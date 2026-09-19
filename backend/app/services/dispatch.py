from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    ClosureStatus,
    Event,
    EventStatus,
    Material,
    MaterialReservation,
    MaterialTransaction,
    RoadClosure,
    Team,
    TeamStatus,
    ValveAction,
    WorkOrder,
    WorkOrderStatus,
)
from .geometry import euclid, point_to_segment_distance
from .impact import affected_users_for, affected_zones_for, boundary_valves_for, estimate_restore
from .materials import (
    MATERIAL_SHORTAGE_DELAY_MIN,
    ROAD_CLOSURE_DETOUR_MIN,
    TRAVEL_SPEED_UNITS_PER_MIN,
    required_materials,
)
from .notifications import material_delay_notification, shutdown_notification

BUSY_TEAM_STATUSES = {
    TeamStatus.enroute,
    TeamStatus.onsite,
    TeamStatus.repairing,
    TeamStatus.blocked_material,
    TeamStatus.blocked_road,
}


def route_blocked(db: Session, x1: float, y1: float, x2: float, y2: float) -> RoadClosure | None:
    """Return the first ACTIVE closure whose segment comes near the travel segment."""
    for closure in db.scalars(select(RoadClosure).where(RoadClosure.status == ClosureStatus.active)).all():
        dist = point_to_segment_distance(
            closure.from_x, closure.from_y, x1, y1, x2, y2
        )
        dist2 = point_to_segment_distance(
            closure.to_x, closure.to_y, x1, y1, x2, y2
        )
        # both endpoints of the closure segment sit on/near the route -> crossing
        if dist < 2.0 and dist2 < 2.0:
            return closure
        mid_x, mid_y = (closure.from_x + closure.to_x) / 2, (closure.from_y + closure.to_y) / 2
        if point_to_segment_distance(mid_x, mid_y, x1, y1, x2, y2) < 1.5:
            return closure
    return None


def evaluate_teams(db: Session, event: Event) -> list[dict]:
    """Rank every team: nearest feasible team first; busy/blocked teams marked infeasible."""
    closures = db.scalars(select(RoadClosure).where(RoadClosure.status == ClosureStatus.active)).all()
    teams = db.scalars(select(Team).order_by(Team.id)).all()
    candidates = []
    for team in teams:
        detour = False
        blocked_reason = ""
        for closure in closures:
            mid_x, mid_y = (closure.from_x + closure.to_x) / 2, (closure.from_y + closure.to_y) / 2
            near = point_to_segment_distance(mid_x, mid_y, team.location_x, team.location_y, event.location_x, event.location_y) < 1.5
            if near:
                detour = True
                blocked_reason = f"路线被 {closure.code} 阻断，需绕行"
                break
        distance = euclid(team.location_x, team.location_y, event.location_x, event.location_y)
        eta = max(5, round(distance / TRAVEL_SPEED_UNITS_PER_MIN) + (ROAD_CLOSURE_DETOUR_MIN if detour else 0))
        feasible = team.status == TeamStatus.available
        reason = ""
        if team.status != TeamStatus.available:
            reason = f"队伍状态为 {team.status.value}，暂不可派"
        elif detour:
            reason = blocked_reason
        candidates.append(
            {
                "team_id": team.id,
                "name": team.name,
                "status": team.status.value if hasattr(team.status, "value") else team.status,
                "distance": round(distance, 1),
                "eta_minutes": eta,
                "route_detour": detour,
                "feasible": feasible,
                "reason": reason,
            }
        )
    # feasible first, then shortest eta
    candidates.sort(key=lambda c: (not c["feasible"], c["eta_minutes"]))
    return candidates


def _material_lookup(db: Session) -> dict[str, Material]:
    return {m.code: m for m in db.scalars(select(Material)).all()}


def check_materials(db: Session, event: Event) -> tuple[dict[str, float], list[dict], bool]:
    needed = required_materials(event.severity.value if hasattr(event.severity, "value") else event.severity,
                                event.pipe_diameter_mm)
    materials = _material_lookup(db)
    shortages = []
    for code, qty in needed.items():
        mat = materials.get(code)
        available = mat.stock if mat else 0
        if available < qty:
            shortages.append(
                {
                    "code": code,
                    "name": mat.name if mat else code,
                    "needed": qty,
                    "available": available,
                    "missing": round(qty - available, 1),
                }
            )
    return needed, shortages, len(shortages) == 0


def dispatch_event(db: Session, event: Event) -> dict:
    candidates = evaluate_teams(db, event)
    feasible = [c for c in candidates if c["feasible"]]
    if not feasible:
        raise ValueError("当前没有空闲抢修队，全部队伍均在作业中")
    choice = feasible[0]
    team = db.get(Team, choice["team_id"])

    needed, shortages, material_ready = check_materials(db, event)
    materials = _material_lookup(db)

    zones = affected_zones_for(db, event)
    valves = boundary_valves_for(db, zones)
    users = affected_users_for(db, zones)

    extra_delay = 0 if material_ready else MATERIAL_SHORTAGE_DELAY_MIN
    if choice["route_detour"]:
        extra_delay += ROAD_CLOSURE_DETOUR_MIN
    eta = estimate_restore(event, len(valves), extra_delay)

    shortage_note = ""
    if shortages:
        shortage_note = "；".join(f"{s['name']}缺{s['missing']}{''}" for s in shortages)

    order = WorkOrder(
        event_id=event.id,
        team_id=team.id,
        status=WorkOrderStatus.assigned,
        planned_eta_minutes=choice["eta_minutes"],
        route_detour=choice["route_detour"],
        material_ready=material_ready,
        shortage_note=shortage_note,
        progress_pct=5,
    )
    db.add(order)
    db.flush()

    # Reserve & deduct materials that ARE available; missing quantities stay flagged.
    for code, qty in needed.items():
        mat = materials.get(code)
        if mat is None:
            continue
        take = min(mat.stock, qty)
        satisfied = mat.stock >= qty
        if take > 0:
            mat.stock -= take
            db.add(
                MaterialTransaction(
                    material_id=mat.id, change=-take, reason=f"工单{order.code}出库", work_order_id=order.id
                )
            )
        db.add(
            MaterialReservation(
                work_order_id=order.id, material_id=mat.id, quantity=qty, satisfied=satisfied
            )
        )

    # Pre-register the valve operations implied by impact analysis
    for valve in valves:
        db.add(ValveAction(event_id=event.id, valve_id=valve.id, action="close", progress_pct=0))

    team.status = TeamStatus.enroute
    team.location_x = team.home_x
    team.location_y = team.home_y
    event.status = EventStatus.dispatched
    event.estimated_restore_at = eta

    shutdown_notification(db, event, users)
    if shortages:
        detail = "、".join(s["name"] for s in shortages)
        material_delay_notification(db, event, users, detail)

    db.commit()
    db.refresh(order)
    return {
        "work_order_id": order.id,
        "work_order_code": order.code,
        "team_id": team.id,
        "team_name": team.name,
        "eta_minutes": choice["eta_minutes"],
        "route_detour": choice["route_detour"],
        "material_ready": material_ready,
        "shortages": shortages,
        "estimated_restore_at": eta,
        "affected_users_count": len(users),
        "candidates": candidates,
    }
