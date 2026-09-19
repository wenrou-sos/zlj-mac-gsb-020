from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    ClosureStatus,
    Event,
    EventStatus,
    Material,
    Pipe,
    RoadClosure,
    Team,
    TeamStatus,
    Valve,
    WaterUser,
    WorkOrder,
    WorkOrderStatus,
    Zone,
)
from ..schemas import (
    DashboardStats,
    FullMap,
    PipeOut,
    TeamOut,
    UserOut,
    ValveOut,
    ZoneOut,
)
from ..services.impact import affected_users_for, affected_zones_for

router = APIRouter(prefix="/api", tags=["resources"])


@router.get("/zones", response_model=list[ZoneOut])
def zones(db: Session = Depends(get_db)):
    return list(db.scalars(select(Zone).order_by(Zone.id)).all())


@router.get("/users", response_model=list[UserOut])
def users(zone_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(WaterUser).order_by(WaterUser.priority.desc(), WaterUser.id)
    if zone_id is not None:
        stmt = stmt.where(WaterUser.zone_id == zone_id)
    return list(db.scalars(stmt).all())


@router.get("/valves", response_model=list[ValveOut])
def valves(db: Session = Depends(get_db)):
    return list(db.scalars(select(Valve).order_by(Valve.id)).all())


@router.get("/pipes", response_model=list[PipeOut])
def pipes(db: Session = Depends(get_db)):
    return list(db.scalars(select(Pipe).order_by(Pipe.id)).all())


@router.get("/teams", response_model=list[TeamOut])
def teams(db: Session = Depends(get_db)):
    return list(db.scalars(select(Team).order_by(Team.id)).all())


@router.get("/map", response_model=FullMap)
def full_map(db: Session = Depends(get_db)):
    return {
        "zones": db.scalars(select(Zone).order_by(Zone.id)).all(),
        "users": db.scalars(select(WaterUser).order_by(WaterUser.id)).all(),
        "valves": db.scalars(select(Valve).order_by(Valve.id)).all(),
        "pipes": db.scalars(select(Pipe).order_by(Pipe.id)).all(),
        "teams": db.scalars(select(Team).order_by(Team.id)).all(),
        "events": db.scalars(select(Event).order_by(Event.id)).all(),
        "closures": db.scalars(select(RoadClosure).where(RoadClosure.status == ClosureStatus.active)).all(),
    }


ACTIVE_EVENT_STATUSES = [
    EventStatus.reported,
    EventStatus.analyzed,
    EventStatus.dispatched,
    EventStatus.repairing,
]
OPEN_ORDER_STATUSES = [
    WorkOrderStatus.assigned,
    WorkOrderStatus.enroute,
    WorkOrderStatus.valves_closed,
    WorkOrderStatus.repairing,
    WorkOrderStatus.blocked_material,
    WorkOrderStatus.blocked_road,
    WorkOrderStatus.pressure_testing,
    WorkOrderStatus.valves_reopened,
]


@router.get("/dashboard", response_model=DashboardStats)
def dashboard(db: Session = Depends(get_db)):
    active_events = list(db.scalars(select(Event).where(Event.status.in_(ACTIVE_EVENT_STATUSES))).all())
    open_orders = list(db.scalars(select(WorkOrder).where(WorkOrder.status.in_(OPEN_ORDER_STATUSES))).all())
    all_teams = db.scalars(select(Team)).all()
    low_stock = [m for m in db.scalars(select(Material)).all() if m.stock <= m.safety_stock]
    closures = db.scalars(select(RoadClosure).where(RoadClosure.status == ClosureStatus.active)).all()

    affected_ids: set[int] = set()
    for event in active_events:
        zones = affected_zones_for(db, event)
        for u in affected_users_for(db, zones):
            affected_ids.add(u.id)

    events_by_severity: dict[str, int] = {}
    for event in active_events:
        key = event.severity.value
        events_by_severity[key] = events_by_severity.get(key, 0) + 1

    events_by_status: dict[str, int] = {}
    for event in active_events:
        events_by_status[event.status.value] = events_by_status.get(event.status.value, 0) + 1

    return {
        "active_events": len(active_events),
        "open_work_orders": len(open_orders),
        "available_teams": sum(1 for t in all_teams if t.status == TeamStatus.available),
        "total_teams": len(all_teams),
        "affected_users_now": len(affected_ids),
        "low_stock_materials": low_stock,
        "active_closures": len(list(closures)),
        "events_by_severity": events_by_severity,
        "events_by_status": events_by_status,
    }
