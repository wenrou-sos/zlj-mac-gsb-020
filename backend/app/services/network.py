"""Pipe-network graph service: routing and affected-area analysis.

The network is an undirected weighted graph (weight = pipe length in metres).
- Dispatch routing runs Dijkstra over the road graph (pipe edges), with edges
  removed where an *active road closure* exists.
- Affected-area analysis simulates isolating valves.  The broken edge is
  removed and each of its two sides is explored independently: the first
  valve reached on every branch forms that side's isolation boundary; if a
  side reaches a water source without crossing a valve it is the live trunk
  side (branch valves must stay open).  Candidate valves are then physically
  closed in a simulation and consumers that lose all source paths are the
  affected population.
"""
import heapq
from collections import deque

from sqlalchemy.orm import Session

from .. import models


def build_graph(db: Session, include_closed_valves: bool = True,
                closures: set[tuple[int, int]] | None = None):
    """Return (adj, edge_len, nodes).

    adj[node_id] = list of neighbor ids; edge_len[(a,b)] sorted tuple -> metres.
    When ``include_closed_valves`` is False, closed valves block flow.
    """
    closures = closures or set()
    nodes = {n.id: n for n in db.query(models.NetworkNode).all()}
    adj: dict[int, list[int]] = {nid: [] for nid in nodes}
    edge_len: dict[tuple[int, int], float] = {}

    for p in db.query(models.Pipe).all():
        key = tuple(sorted((p.start_node_id, p.end_node_id)))
        a, b = nodes.get(p.start_node_id), nodes.get(p.end_node_id)
        if a is None or b is None:
            continue
        if key in closures:  # road closures block vehicle routing
            continue
        if not include_closed_valves:
            if (a.type == "valve" and not a.is_open) or (b.type == "valve" and not b.is_open):
                continue
        adj[p.start_node_id].append(p.end_node_id)
        adj[p.end_node_id].append(p.start_node_id)
        edge_len[key] = p.length_m
    return adj, edge_len, nodes


def active_closures(db: Session) -> set[tuple[int, int]]:
    rows = db.query(models.RoadClosure).filter(models.RoadClosure.active.is_(True)).all()
    return {tuple(sorted((r.start_node_id, r.end_node_id))) for r in rows}


def shortest_path(adj, edge_len, src: int, dst: int):
    """Dijkstra. Returns (distance_m, [node_ids]) or (None, None) if unreachable."""
    if src not in adj or dst not in adj:
        return None, None
    if src == dst:
        return 0.0, [src]
    dist = {src: 0.0}
    prev: dict[int, int] = {}
    pq = [(0.0, src)]
    visited = set()
    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        if u == dst:
            break
        for v in adj[u]:
            nd = d + edge_len[tuple(sorted((u, v)))]
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    if dst not in dist:
        return None, None
    path = [dst]
    while path[-1] != src:
        path.append(prev[path[-1]])
    path.reverse()
    return dist[dst], path


def _side_boundary(adj, nodes, start: int, other: int) -> tuple[str, set[int]]:
    """Explore one side of the broken pipe.

    Returns ("valves", {...}) when the side can be sealed by closing the
    first valve on each outward branch, or ("source", set()) when it is
    directly fed by a source without crossing any valve (live trunk side).
    """
    start_node = nodes.get(start)
    if start_node and start_node.type == "valve":
        # endpoint itself is a valve — closing it seals this side
        return "valves", {start}

    broken = tuple(sorted((start, other)))
    seen = {start}
    q = deque([start])
    valves: set[int] = set()
    reached_source = False
    while q:
        u = q.popleft()
        for v in adj[u]:
            if tuple(sorted((u, v))) == broken or v in seen:
                continue
            seen.add(v)
            n = nodes.get(v)
            if n is None:
                continue
            if n.type == "valve":
                valves.add(v)          # seal here, do not cross
            elif n.type == "source":
                reached_source = True  # live trunk, stop this branch
            else:
                q.append(v)
    if reached_source:
        return "source", set()
    return "valves", valves


def analyze_affected_area(db: Session, pipe: models.Pipe) -> dict:
    """Compute the outage footprint if ``pipe`` were isolated for repair."""
    adj, edge_len, nodes = build_graph(db)
    a, b = pipe.start_node_id, pipe.end_node_id

    warnings: list[str] = []

    # 1. Isolation boundary on each side of the break
    kind_a, valves_a = _side_boundary(adj, nodes, a, b)
    kind_b, valves_b = _side_boundary(adj, nodes, b, a)
    valves = valves_a | valves_b
    if kind_a == "source" or kind_b == "source":
        warnings.append("破损管段一侧直接连通水厂且干管无阀门，维修时需厂端降压或短时关源")
    if not valves:
        warnings.append("破损管段两侧均未找到隔离阀，需扩大停水范围")

    # 2. Simulate: remove broken edge + all edges incident to closed valves
    blocked_edges = {tuple(sorted((a, b)))}
    for v in valves:
        for nb in adj[v]:
            blocked_edges.add(tuple(sorted((v, nb))))

    hyd_adj: dict[int, list[int]] = {nid: [] for nid in nodes}
    for (u, v) in edge_len:
        if tuple(sorted((u, v))) in blocked_edges:
            continue
        hyd_adj[u].append(v)
        hyd_adj[v].append(u)

    # 3. Nodes still reachable from any source keep water
    sources = [nid for nid, n in nodes.items() if n.type == "source"]
    has_water: set[int] = set()
    for s in sources:
        q = deque([s])
        has_water.add(s)
        while q:
            u = q.popleft()
            for v in hyd_adj.get(u, []):
                if v not in has_water:
                    has_water.add(v)
                    q.append(v)

    # 4. Consumers without water = affected
    consumers = db.query(models.Consumer).all()
    affected = [c for c in consumers if c.node_id not in has_water]

    # 5. Does an alternative feed path exist for the broken edge (loop network)?
    alt_distance, _ = shortest_path(hyd_adj, edge_len, a, b)

    return {
        "isolation_valve_ids": sorted(valves),
        "affected_consumer_ids": [c.id for c in affected],
        "affected_consumers": [
            {"id": c.id, "code": c.code, "name": c.name,
             "category": c.category, "residents": c.residents}
            for c in affected
        ],
        "affected_residents": sum(c.residents for c in affected),
        "alternative_route_available": alt_distance is not None,
        "warnings": warnings,
    }
