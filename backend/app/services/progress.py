from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    ClosureStatus,
    Event,
    EventStatus,
    Material,
    MaterialReservation,
    MaterialTransaction,
    Notification,
    RoadClosure,
    TeamStatus,
    Valve,
    ValveAction,
    WaterUser,
    WorkOrder,
    WorkOrderStatus,
)
from ..services.geometry import point_to_segment_distance
from .impact import affected_users_for
from .materials import MATERIAL_SHORTAGE_DELAY_MIN, ROAD_CLOSURE_DETOUR_MIN
from .notifications import restored_notification, road_detour_notification

# action -> (progress %, human label)
ACTION_PROGRESS = {
    "depart": (15, "抢修队出发"),
    "arrive": (25, "抢修队到达现场"),
    "close_valves": (35, "边界阀门已关闭，开始停水"),
    "start_repair": (50, "开始开挖修复"),
    "repair_update": (65, "修复作业推进中"),
    "pressure_test": (85, "管道修复完成，正在打压测试"),
    "reopen_valves": (95, "阀门开启，逐步恢复供水"),
    "complete": (100, "抢修完成，现场清理完毕"),
}

TERMINAL_PREVIOUS = {
    "depart": {WorkOrderStatus.assigned, WorkOrderStatus.blocked_road},
    "arrive": {WorkOrderStatus.enroute},
    "close_valves": {WorkOrderStatus.enroute, WorkOrderStatus.valves_closed},
    "start_repair": {WorkOrderStatus.valves_closed, WorkOrderStatus.repairing, WorkOrderStatus.blocked_material},
    "repair_update": {WorkOrderStatus.repairing},
    "pressure_test": {WorkOrderStatus.repairing},
    "reopen_valves": {WorkOrderStatus.pressure_testing, WorkOrderStatus.valves_reopened},
    "complete": {WorkOrderStatus.valves_reopened, WorkOrderStatus.completed},
}


def _push_eta(event: Event, minutes: int) -> None:
    base = event.estimated_restore_at or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    event.estimated_restore_at = base + timedelta(minutes=minutes)


def _affected_users(db: Session, event: Event) -> list[WaterUser]:
    from .impact import affected_zones_for

    return affected_users_for(db, affected_zones_for(db, event))


def report_material_block(db: Session, order: WorkOrder, note: str) -> WorkOrder:
    """Crew reports missing material on site: block the job, push ETA, notify users."""
    event = order.event
    order.status = WorkOrderStatus.blocked_material
    order.material_ready = False
    if note:
        order.shortage_note = note
    order.progress_pct = max(order.progress_pct, 45)
    order.team.status = TeamStatus.blocked_material
    _push_eta(event, MATERIAL_SHORTAGE_DELAY_MIN)
    users = _affected_users(db, event)
    from .notifications import material_delay_notification

    material_delay_notification(db, event, users, note or "抢修")
    db.flush()
    return order


def receive_materials(db: Session, order: WorkOrder) -> WorkOrder:
    """Allocate currently available stock to this order's unsatisfied reservations."""
    unsatisfied = [r for r in order.reservations if not r.satisfied]
    for res in unsatisfied:
        mat = db.get(Material, res.material_id)
        need = res.quantity
        # count material already consumed by this order
        consumed = sum(
            t.change for t in db.scalars(
                select(MaterialTransaction).where(MaterialTransaction.work_order_id == order.id)
            ).all() if t.material_id == mat.id
        )
        outstanding = need + min(0.0, consumed)
        if mat.stock >= outstanding:
            mat.stock -= outstanding
            res.satisfied = True
            db.add(
                MaterialTransaction(
                    material_id=mat.id, change=-outstanding, reason=f"工单{order.code}补料到货出库",
                    work_order_id=order.id,
                )
            )
    db.flush()
    still_missing = [r for r in order.reservations if not r.satisfied]
    if not still_missing:
        order.material_ready = True
        order.shortage_note = ""
        if order.status == WorkOrderStatus.blocked_material:
            order.status = WorkOrderStatus.repairing
            order.team.status = TeamStatus.repairing
    return order


def apply_action(db: Session, order: WorkOrder, action: str, note: str = "") -> WorkOrder:
    event = order.event

    if action == "report_material_shortage":
        db.flush()
        return report_material_block(db, order, note)

    if action == "materials_received":
        return receive_materials(db, order)

    if action not in ACTION_PROGRESS:
        raise ValueError(f"未知的进度动作: {action}")

    allowed = TERMINAL_PREVIOUS.get(action, set())
    if allowed and order.status not in allowed:
        raise ValueError(f"工单当前状态 {order.status.value} 不允许执行动作 {action}")

    pct, label = ACTION_PROGRESS[action]

    if action == "depart":
        order.status = WorkOrderStatus.enroute
        order.team.status = TeamStatus.enroute
    elif action == "arrive":
        order.team.status = TeamStatus.onsite
        # remain enroute until valves are closed
    elif action == "close_valves":
        order.status = WorkOrderStatus.valves_closed
        _operate_valves(db, event, close=True)
        event.status = EventStatus.repairing
    elif action == "start_repair":
        order.status = WorkOrderStatus.repairing
        order.team.status = TeamStatus.repairing
    elif action == "repair_update":
        order.status = WorkOrderStatus.repairing
    elif action == "pressure_test":
        order.status = WorkOrderStatus.pressure_testing
    elif action == "reopen_valves":
        order.status = WorkOrderStatus.valves_reopened
        _operate_valves(db, event, close=False)
    elif action == "complete":
        order.status = WorkOrderStatus.completed
        order.progress_pct = 100
        order.completed_at = datetime.now(timezone.utc)
        order.team.status = TeamStatus.available
        order.team.location_x = order.team.home_x
        order.team.location_y = order.team.home_y
        event.status = EventStatus.restored
        users = _affected_users(db, event)
        restored_notification(db, event, users)

    if action != "complete":
        order.progress_pct = max(order.progress_pct, pct)
    db.flush()
    return order


def _operate_valves(db: Session, event: Event, close: bool) -> None:
    va_actions = db.scalars(select(ValveAction).where(ValveAction.event_id == event.id)).all()
    for va in va_actions:
        if close and va.action == "close" and not va.completed:
            va.completed = True
            va.progress_pct = 100
            va.valve.is_open = False
        elif not close:
            if va.action == "close":
                va.valve.is_open = True
            # record the reopen op once
            exists = any(a.action == "reopen" and a.valve_id == va.valve_id for a in va_actions)
            if not exists:
                db.add(
                    ValveAction(
                        event_id=event.id, valve_id=va.valve_id, action="reopen",
                        progress_pct=100, completed=True,
                    )
                )


# ---------- road closure replanning ----------

def order_route_blocked(db: Session, order: WorkOrder, closure: RoadClosure) -> bool:
    team = order.team
    event = order.event
    mid_x, mid_y = (closure.from_x + closure.to_x) / 2, (closure.from_y + closure.to_y) / 2
    return point_to_segment_distance(
        mid_x, mid_y, team.location_x, team.location_y, event.location_x, event.location_y
    ) < 1.5


def apply_closure_replan(db: Session, closure: RoadClosure) -> dict:
    """Adjust every in-flight work order whose route crosses the new closure."""
    orders = db.scalars(
        select(WorkOrder).where(
            WorkOrder.status.in_(
                [WorkOrderStatus.assigned, WorkOrderStatus.enroute, WorkOrderStatus.blocked_road]
            )
        )
    ).all()

    adjusted = []
    notified_total = 0
    for order in orders:
        if not order_route_blocked(db, order, closure):
            continue
        order.route_detour = True
        order.planned_eta_minutes += ROAD_CLOSURE_DETOUR_MIN
        order.status = WorkOrderStatus.blocked_road
        order.team.status = TeamStatus.blocked_road
        order.progress_pct = max(order.progress_pct, 10)
        _push_eta(order.event, ROAD_CLOSURE_DETOUR_MIN)

        users = _affected_users(db, order.event)
        created = road_detour_notification(db, order.event, users, closure.reason)
        notified_total += len(created)
        adjusted.append(
            {
                "work_order_id": order.id,
                "work_order_code": order.code,
                "event_code": order.event.code,
                "extra_eta_minutes": ROAD_CLOSURE_DETOUR_MIN,
                "affected_users": len(users),
            }
        )
    db.commit()
    return {"closure_id": closure.id, "adjusted_orders": adjusted, "notified_users_count": notified_total}


def resolve_closure(db: Session, closure: RoadClosure) -> dict:
    closure.status = ClosureStatus.resolved
    resumed = []
    orders = db.scalars(select(WorkOrder).where(WorkOrder.status == WorkOrderStatus.blocked_road)).all()
    for order in orders:
        # ensure no other active closure still blocks it
        still_blocked = False
        for other in db.scalars(select(RoadClosure).where(RoadClosure.status == ClosureStatus.active)).all():
            if other.id != closure.id and order_route_blocked(db, order, other):
                still_blocked = True
                break
        if not still_blocked:
            order.status = WorkOrderStatus.enroute
            order.team.status = TeamStatus.enroute
            resumed.append(order.code)
    db.commit()
    return {"closure_id": closure.id, "resumed_orders": resumed}
