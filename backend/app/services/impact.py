from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Event, Severity, Valve, WaterUser, Zone
from ..services.geometry import euclid, parse_polygon, point_in_polygon
from ..services.materials import REPAIR_MINUTES, VALVE_MINUTES

# severity -> extra neighbor zones pulled in besides the zone containing the leak
SEVERITY_SPREAD = {
    Severity.minor: 0,
    Severity.moderate: 1,
    Severity.moderate.value: 1,
    Severity.major: 1,
    Severity.major.value: 1,
    Severity.critical: 2,
    Severity.critical.value: 2,
}

SEVERITY_LABEL = {
    "minor": "轻微",
    "moderate": "一般",
    "major": "较大",
    "critical": "重大",
}


def locate_zone(db: Session, x: float, y: float) -> Zone | None:
    for zone in db.scalars(select(Zone)).all():
        if point_in_polygon(x, y, parse_polygon(zone.polygon)):
            return zone
    # fallback: nearest centroid
    zones = db.scalars(select(Zone)).all()
    return min(zones, key=lambda z: euclid(x, y, z.centroid_x, z.centroid_y), default=None)


def affected_zones_for(db: Session, event: Event) -> list[Zone]:
    """Zones that must be isolated for the repair (home zone + neighbours by severity)."""
    home = locate_zone(db, event.location_x, event.location_y)
    if home is None:
        return []

    spread = 0
    if isinstance(event.severity, Severity):
        spread = SEVERITY_SPREAD.get(event.severity, 0)
    else:
        spread = SEVERITY_SPREAD.get(event.severity, 0)

    if spread == 0:
        return [home]

    others = [z for z in db.scalars(select(Zone)).all() if z.id != home.id]
    others.sort(key=lambda z: euclid(event.location_x, event.location_y, z.centroid_x, z.centroid_y))
    return [home, *others[:spread]]


def boundary_valves_for(db: Session, zones: list[Zone]) -> list[Valve]:
    """Valves bounding the affected area: every valve attached to an affected zone."""
    zone_ids = {z.id for z in zones}
    valves = db.scalars(select(Valve)).all()
    return [v for v in valves if zone_ids & {z.id for z in v.zones}]


def affected_users_for(db: Session, zones: list[Zone]) -> list[WaterUser]:
    zone_ids = [z.id for z in zones]
    return list(
        db.scalars(select(WaterUser).where(WaterUser.zone_id.in_(zone_ids)).order_by(WaterUser.priority.desc())).all()
    )


def estimate_restore(event: Event, valve_count: int, extra_minutes: int = 0) -> datetime:
    repair = REPAIR_MINUTES[event.severity.value if isinstance(event.severity, Severity) else event.severity]
    total = repair + valve_count * VALVE_MINUTES * 2 + extra_minutes  # close + reopen
    return datetime.now(timezone.utc) + timedelta(minutes=total)


def build_impact_report(db: Session, event: Event, extra_delay_minutes: int = 0) -> dict:
    zones = affected_zones_for(db, event)
    valves = boundary_valves_for(db, zones)
    users = affected_users_for(db, zones)
    eta = estimate_restore(event, len(valves), extra_delay_minutes)
    repair = REPAIR_MINUTES[event.severity.value if isinstance(event.severity, Severity) else event.severity]
    return {
        "event_id": event.id,
        "severity": event.severity.value if isinstance(event.severity, Severity) else event.severity,
        "affected_zones": zones,
        "affected_users": users,
        "affected_users_count": len(users),
        "priority_users_count": sum(1 for u in users if u.priority),
        "valves_to_close": valves,
        "estimated_restore_at": eta,
        "estimated_repair_minutes": repair + len(valves) * VALVE_MINUTES * 2 + extra_delay_minutes,
    }
