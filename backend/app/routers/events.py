from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Event, EventStatus, Severity
from ..schemas import EventCreate, EventOut, ImpactReport
from ..services.impact import build_impact_report

router = APIRouter(prefix="/api/events", tags=["events"])

VALID_SEVERITIES = {s.value for s in Severity}


@router.get("", response_model=list[EventOut])
def list_events(db: Session = Depends(get_db)):
    return list(db.scalars(select(Event).order_by(Event.created_at.desc())).all())


@router.post("", response_model=EventOut, status_code=201)
def create_event(payload: EventCreate, db: Session = Depends(get_db)):
    if payload.severity not in VALID_SEVERITIES:
        raise HTTPException(422, f"severity 必须是 {sorted(VALID_SEVERITIES)} 之一")
    event = Event(
        title=payload.title,
        description=payload.description,
        reporter=payload.reporter,
        reporter_phone=payload.reporter_phone,
        location_x=payload.location_x,
        location_y=payload.location_y,
        address=payload.address,
        severity=Severity(payload.severity),
        pipe_diameter_mm=payload.pipe_diameter_mm,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "事件不存在")
    return event


@router.post("/{event_id}/analyze", response_model=ImpactReport)
def analyze_event(event_id: int, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "事件不存在")
    report = build_impact_report(db, event)
    if event.status == EventStatus.reported:
        event.status = EventStatus.analyzed
        event.estimated_restore_at = report["estimated_restore_at"]
        db.commit()
    return report
