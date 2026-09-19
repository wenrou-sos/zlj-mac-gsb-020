from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Event, WorkOrder
from ..schemas import DispatchRequest, DispatchResult
from ..services.dispatch import check_materials, dispatch_event, evaluate_teams

router = APIRouter(prefix="/api/dispatch", tags=["dispatch"])


@router.get("/candidates/{event_id}")
def candidates(event_id: int, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "事件不存在")
    needed, shortages, ready = check_materials(db, event)
    return {
        "candidates": evaluate_teams(db, event),
        "required_materials": needed,
        "shortages": shortages,
        "material_ready": ready,
    }


@router.post("", response_model=DispatchResult)
def dispatch(payload: DispatchRequest, db: Session = Depends(get_db)):
    event = db.get(Event, payload.event_id)
    if not event:
        raise HTTPException(404, "事件不存在")
    if event.work_orders:
        raise HTTPException(409, f"该事件已派工：工单 {event.work_orders[0].code}")
    try:
        return dispatch_event(db, event)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
