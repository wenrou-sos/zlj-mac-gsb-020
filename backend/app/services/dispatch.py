"""Dispatch / repair-planning service.

Covers team assignment, material reservation, automatic re-planning on
road closures and material shortages, and stop/restart-water progress.
"""
from datetime import datetime

from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session

from .. import models
from .network import active_closures, build_graph, shortest_path

# --- Planning tables --------------------------------------------------------

MATERIAL_BOM = {
    # severity -> {material_code: qty}
    "low":    {"pipe_dn100": 1, "coupler": 2, "seal": 4},
    "medium": {"pipe_dn300": 2, "coupler": 4, "seal": 8, "valve_dn300": 0},
    "high":   {"pipe_dn500": 3, "coupler": 6, "seal": 16, "valve_dn300": 1, "pump": 1},
}

REPAIR_MINUTES = {"low": 90, "medium": 180, "high": 300}
ROUTE_SPEED_M_PER_MIN = 400.0  # urban average repair-vehicle speed
MAX_REASONABLE_ETA_MIN = 120   # detours beyond this trigger team reassignment


# --- Helpers ----------------------------------------------------------------

def _material_demand(severity: str) -> dict:
    return dict(MATERIAL_BOM.get(severity, MATERIAL_BOM["medium"]))


def _material_map(db: Session) -> dict:
    return {m.code: m for m in db.query(models.Material).all()}


def add_event(db: Session, wo: models.WorkOrder, etype: str, message: str):
    db.add(models.WorkOrderEvent(work_order_id=wo.id, type=etype, message=message))


def notify(db: Session, incident: models.Incident, title: str, message: str,
           scope: str = "users", channel: str = "sms", wo: models.WorkOrder | None = None):
    db.add(models.Notification(
        incident_id=incident.id,
        work_order_id=wo.id if wo else None,
        scope=scope, channel=channel, title=title, message=message,
        affected_consumer_ids=incident.affected_consumer_ids or [],
        affected_residents=incident.affected_residents or 0,
    ))


def _team_route(db: Session, team: models.RepairTeam, incident: models.Incident,
                closures) -> tuple[float | None, list[int]]:
    """Shortest road route from team position/base to the broken pipe."""
    adj, edge_len, nodes = build_graph(db, closures=closures)
    pipe = incident.pipe
    if pipe is None:
        return None, []
    src = team.base_node_id
    if src is None:
        # fall back to nearest graph node by Euclidean distance
        src = min(nodes, key=lambda nid: (nodes[nid].x - team.x) ** 2 + (nodes[nid].y - team.y) ** 2)
    # target = closer endpoint of the broken pipe
    d1, p1 = shortest_path(adj, edge_len, src, pipe.start_node_id)
    d2, p2 = shortest_path(adj, edge_len, src, pipe.end_node_id)
    if d1 is None and d2 is None:
        return None, []
    if d2 is None or (d1 is not None and d1 <= d2):
        return d1, p1
    return d2, p2


def reserve_materials(db: Session, wo: models.WorkOrder, demand: dict) -> list[models.MaterialShortage]:
    """Reserve what is available; record shortages for the rest."""
    mats = _material_map(db)
    shortages = []
    for code, qty in demand.items():
        mat = mats.get(code)
        avail = mat.stock if mat else 0.0
        take = min(avail, qty)
        if mat and take > 0:
            mat.stock -= take
        missing = qty - take
        if missing > 0.001:
            sh = models.MaterialShortage(
                work_order_id=wo.id, material_code=code,
                required_qty=qty, available_qty=avail,
            )
            db.add(sh)
            shortages.append(sh)
    return shortages


# --- Core actions -----------------------------------------------------------

def dispatch(db: Session, incident: models.Incident) -> models.WorkOrder:
    """Create the work order and assign the fastest reachable team."""
    closures = active_closures(db)
    teams = db.query(models.RepairTeam).order_by(models.RepairTeam.id).all()

    ranked = []
    for t in teams:
        dist, path = _team_route(db, t, incident, closures)
        if dist is None:
            ranked.append((float("inf"), [], None, t))
        else:
            eta = max(1, int(round(dist / ROUTE_SPEED_M_PER_MIN)))
            ranked.append((dist, path, eta, t))
    ranked.sort(key=lambda r: r[0])

    dist, path, eta, team = ranked[0]
    demand = _material_demand(incident.severity)
    repair_min = REPAIR_MINUTES[incident.severity]

    wo = models.WorkOrder(
        incident_id=incident.id,
        team_id=team.id if dist != float("inf") else None,
        status=models.WO_EN_ROUTE if dist != float("inf") else models.WO_PLANNED,
        material_demand=demand,
        route_node_ids=path,
        route_distance_m=dist if dist != float("inf") else 0.0,
        eta_minutes=(eta or 0),
        repair_minutes=repair_min,
        plan_summary=f"抢修 {incident.title}：预计到场 {(eta or 0)} 分钟，修复约 {repair_min} 分钟。",
    )
    db.add(wo)
    db.flush()

    # reserve materials
    shortages = reserve_materials(db, wo, demand)

    if dist == float("inf"):
        wo.replan_reason = "所有抢修队均无法到达（道路封闭），等待调度"
        add_event(db, wo, "road_closure", "无可达路线，抢修队暂无法派工")
    else:
        team.status = models.TEAM_ASSIGNED
        team.current_work_order_id = wo.id
        incident.status = models.INCIDENT_DISPATCHED
        add_event(db, wo, "status_change",
                  f"已派工至 {team.name}，路线 {len(path)} 个节点、约 {dist:.0f}m，ETA {eta} 分钟")

    if shortages:
        wo.status = models.WO_DELAYED_MATERIAL
        codes = "、".join(s.material_code for s in shortages)
        wo.replan_reason = f"物料不足：{codes}，已发起紧急调拨"
        add_event(db, wo, "material", f"库存不足物料：{codes}；维修开始时间将后延")
        notify(db, incident, "停水时间可能延长",
               f"因抢修物料 ({codes}) 库存不足，正在紧急跨站调拨，"
               f"预计影响 {incident.affected_residents} 名居民，请提前储水。",
               wo=wo)
    else:
        notify(db, incident, "抢修已派工",
               f"抢修队已出发，预计 {wo.eta_minutes} 分钟后到场，"
               f"计划修复时长约 {repair_min} 分钟，期间该区域暂停供水。",
               wo=wo)

    incident.estimated_outage_minutes = wo.eta_minutes + repair_min
    db.flush()
    return wo


def replan_for_closure(db: Session, closure: models.RoadClosure):
    """Re-route every active work order after a road is closed.

    - reroute the same team when an alternative path exists (ETA updated);
    - when the detour is too long or the team is cut off, reassign the work
      order to the fastest now-reachable team;
    - push user notifications describing the new impact range.
    """
    closures = active_closures(db)
    wos = (
        db.query(models.WorkOrder)
        .options(selectinload(models.WorkOrder.incident), selectinload(models.WorkOrder.team))
        .filter(models.WorkOrder.status.in_(
            [models.WO_EN_ROUTE, models.WO_PLANNED, models.WO_DELAYED_MATERIAL]))
        .all()
    )
    for wo in wos:
        incident = wo.incident
        if wo.team_id is None:
            # maybe a team can now reach after closures change
            new_dist, new_path, new_eta, new_team = _best_team(db, incident, closures, exclude_id=None)
            if new_team is not None:
                _assign_team(db, wo, new_team, new_dist, new_path, new_eta)
                add_event(db, wo, "road_closure", "道路封闭解除后重新派工成功")
            continue

        cur_team = wo.team
        dist, path = _team_route(db, cur_team, incident, closures)

        if dist is not None:
            new_eta = max(1, int(round(dist / ROUTE_SPEED_M_PER_MIN)))
            if path != (wo.route_node_ids or []):
                wo.diverted = True
                wo.replan_reason = f"道路封闭：{closure.reason}，已改道"
                wo.route_node_ids = path
                wo.route_distance_m = dist
                wo.eta_minutes = new_eta
                add_event(db, wo, "road_closure",
                          f"因「{closure.reason}」改道，新路线 {dist:.0f}m，ETA 更新为 {new_eta} 分钟")
                if new_eta > MAX_REASONABLE_ETA_MIN:
                    _try_reassign(db, wo, incident, closures, cur_team.id,
                                  reason=f"绕行后 ETA {new_eta} 分钟超出阈值")
                _notify_closure(db, wo, incident, new_eta, reachable=True)
        else:
            _try_reassign(db, wo, incident, closures, cur_team.id,
                          reason=f"道路封闭「{closure.reason}」导致原抢修队无路可达")

    db.flush()


def _best_team(db, incident, closures, exclude_id):
    best = (None, None, None, None)
    teams = db.query(models.RepairTeam).filter(models.RepairTeam.id != exclude_id).all()
    ranked = []
    for t in teams:
        dist, path = _team_route(db, t, incident, closures)
        if dist is None:
            continue
        eta = max(1, int(round(dist / ROUTE_SPEED_M_PER_MIN)))
        ranked.append((dist, path, eta, t))
    ranked.sort(key=lambda r: r[0])
    return ranked[0] if ranked else best


def _assign_team(db, wo, team, dist, path, eta):
    team.status = models.TEAM_ASSIGNED
    team.current_work_order_id = wo.id
    wo.team_id = team.id
    wo.route_node_ids = path
    wo.route_distance_m = dist
    wo.eta_minutes = eta
    if wo.status == models.WO_PLANNED:
        wo.status = models.WO_EN_ROUTE


def _try_reassign(db, wo, incident, closures, old_team_id, reason):
    dist, path, eta, new_team = _best_team(db, incident, closures, exclude_id=old_team_id)
    if new_team is None:
        wo.status = models.WO_PLANNED
        wo.team_id = None
        wo.replan_reason = reason + "；且暂无其他可达抢修队"
        add_event(db, wo, "road_closure", reason + "，无替代队伍，等待道路解封")
        _notify_closure(db, wo, incident, None, reachable=False)
        old = db.get(models.RepairTeam, old_team_id)
        if old:
            old.status = models.TEAM_IDLE
            old.current_work_order_id = None
        return

    old = db.get(models.RepairTeam, old_team_id)
    if old:
        old.status = models.TEAM_IDLE
        old.current_work_order_id = None
    _assign_team(db, wo, new_team, dist, path, eta)
    wo.diverted = True
    wo.status = models.WO_EN_ROUTE
    wo.replan_reason = reason + f"，改派 {new_team.name}"
    add_event(db, wo, "road_closure",
              f"{reason}，抢修任务由 {new_team.name} 接手，ETA {eta} 分钟")
    _notify_closure(db, wo, incident, eta, reachable=True, reassigned=True)


def _notify_closure(db, wo, incident, eta, reachable, reassigned=False):
    if reachable:
        tail = "抢修队已改派。" if reassigned else "抢修队已规划绕行路线。"
        msg = (f"因道路封闭，{tail}预计到场时间 {eta} 分钟，"
               f"停水影响范围维持 {incident.affected_residents} 名居民不变。")
        title = "道路封闭：抢修计划已调整"
    else:
        msg = (f"道路封闭导致抢修队无法进入现场，正在协调交管解封；"
               f"受影响 {incident.affected_residents} 名居民的停水时间将延长，"
               f"建议启用应急供水点。")
        title = "道路封闭：抢修受阻，停水时间延长"
    notify(db, incident, title, msg, wo=wo, scope="users", channel="sms")


# --- Progress transitions ---------------------------------------------------

def advance_work_order(db: Session, wo: models.WorkOrder, note: str | None = None) -> models.WorkOrder:
    """Drive the stop-water / repair / restart-water lifecycle one step."""
    incident = db.get(models.Incident, wo.incident_id)
    if wo.status == models.WO_EN_ROUTE:
        wo.status = models.WO_ON_SITE
        wo.team.status = models.TEAM_ON_SITE
        add_event(db, wo, "status_change", "抢修队到场，开始关阀停水")
        # physically close the isolation valves
        for vid in incident.isolation_valve_ids or []:
            v = db.get(models.NetworkNode, vid)
            if v:
                v.is_open = False
        wo.water_off = True
        incident.status = models.INCIDENT_REPAIRING
        add_event(db, wo, "status_change", "隔离阀已关闭，区域停水")
        notify(db, incident, "停水通知",
               f"受影响区域现已停水，涉及 {incident.affected_residents} 名居民，"
               f"预计 {wo.repair_minutes} 分钟后恢复供水。", wo=wo)
    elif wo.status in (models.WO_ON_SITE, models.WO_REPAIRING):
        wo.status = models.WO_REPAIRING
        if not wo.started_at:
            wo.started_at = datetime.utcnow()
        add_event(db, wo, "status_change", note or "维修作业进行中（换管/接口/密封）")
    elif wo.status == models.WO_DELAYED_MATERIAL:
        add_event(db, wo, "material", note or "仍在等待调拨物料")
    else:
        add_event(db, wo, "comment", note or "工单当前状态无需推进")
    db.flush()
    return wo


def complete_work_order(db: Session, wo: models.WorkOrder) -> models.WorkOrder:
    incident = db.get(models.Incident, wo.incident_id)
    # reopen valves -> water restored
    for vid in incident.isolation_valve_ids or []:
        v = db.get(models.NetworkNode, vid)
        if v:
            v.is_open = True
    wo.status = models.WO_COMPLETED
    wo.water_off = False
    wo.completed_at = datetime.utcnow()
    if wo.team:
        wo.team.status = models.TEAM_IDLE
        wo.team.current_work_order_id = None
    incident.status = models.INCIDENT_REPAIRED
    add_event(db, wo, "status_change", "维修完成，阀门开启，恢复供水")
    notify(db, incident, "复水通知",
           f"抢修已完成，受影响区域供水已恢复，如水质短时浑浊请放水片刻后使用。",
           wo=wo, scope="users", channel="sms")
    db.flush()
    return wo


def report_material_shortage(db: Session, wo: models.WorkOrder, material_code: str,
                             required_qty: float) -> models.MaterialShortage:
    """On-site discovery that a material is missing mid-repair."""
    mats = _material_map(db)
    mat = mats.get(material_code)
    avail = mat.stock if mat else 0.0
    sh = models.MaterialShortage(
        work_order_id=wo.id, material_code=material_code,
        required_qty=required_qty, available_qty=avail,
    )
    db.add(sh)
    wo.status = models.WO_DELAYED_MATERIAL
    wo.replan_reason = f"现场缺料：{material_code} 需 {required_qty}，库存 {avail}"
    incident = db.get(models.Incident, wo.incident_id)
    add_event(db, wo, "material",
              f"现场报告物料 {material_code} 不足（需 {required_qty}，库存 {avail}），启动紧急调拨")
    notify(db, incident, "物料不足：复水时间调整",
           f"抢修现场缺少 {material_code}，已从邻站紧急调运；"
           f"停水将延长，影响 {incident.affected_residents} 名居民，"
           f"平台已向该范围用户推送延迟复水通知。", wo=wo)
    db.flush()
    return sh


def restock_and_retry(db: Session, material_code: str, qty: float):
    """Add stock; release every work order that was waiting on this material."""
    mat = _material_map(db).get(material_code)
    if mat is None:
        raise ValueError(f"unknown material {material_code}")
    mat.stock += qty

    open_shortages = (
        db.query(models.MaterialShortage)
        .filter(models.MaterialShortage.material_code == material_code,
                models.MaterialShortage.resolved.is_(False))
        .all()
    )
    resolved_wos = set()
    for sh in open_shortages:
        sh.resolved = True
        sh.resolved_at = datetime.utcnow()
        resolved_wos.add(sh.work_order_id)

    for wo_id in resolved_wos:
        wo = db.get(models.WorkOrder, wo_id)
        if not wo or wo.status != models.WO_DELAYED_MATERIAL:
            continue
        still_missing = (
            db.query(models.MaterialShortage)
            .filter(models.MaterialShortage.work_order_id == wo_id,
                    models.MaterialShortage.resolved.is_(False))
            .count()
        )
        if still_missing == 0:
            wo.status = models.WO_EN_ROUTE if not wo.started_at else models.WO_REPAIRING
            wo.replan_reason = None
            incident = db.get(models.Incident, wo.incident_id)
            add_event(db, wo, "material", "调拨物料到位，抢修继续")
            notify(db, incident, "物料到位：抢修恢复",
                   "调拨物料已送达现场，抢修作业恢复，将按新的预计时间复水。", wo=wo)
    db.flush()
    return len(resolved_wos)
