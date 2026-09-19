from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services import dispatch

router = APIRouter(tags=["disruptions"])


@router.get("/road-closures", response_model=list[schemas.RoadClosureOut])
def list_closures(active_only: bool = False, db: Session = Depends(get_db)):
    q = db.query(models.RoadClosure)
    if active_only:
        q = q.filter(models.RoadClosure.active.is_(True))
    return q.order_by(models.RoadClosure.id.desc()).all()


@router.post("/road-closures", response_model=schemas.RoadClosureOut, status_code=201)
def create_closure(body: schemas.RoadClosureCreate, db: Session = Depends(get_db)):
    """登记道路封闭，系统自动重算所有在途工单的路线/ETA 并改派、通知。"""
    # validate endpoints and that they belong to a pipe (roads follow pipes)
    ids = {body.start_node_id, body.end_node_id}
    pipe = (
        db.query(models.Pipe)
        .filter(
            ((models.Pipe.start_node_id == body.start_node_id)
             & (models.Pipe.end_node_id == body.end_node_id))
            | ((models.Pipe.start_node_id == body.end_node_id)
               & (models.Pipe.end_node_id == body.start_node_id))
        )
        .first()
    )
    if pipe is None:
        raise HTTPException(status_code=400, detail="封闭路段必须沿管网管段设置")
    dup = (
        db.query(models.RoadClosure)
        .filter(models.RoadClosure.active.is_(True),
                models.RoadClosure.pipe_id == pipe.id)
        .first()
    )
    if dup:
        raise HTTPException(status_code=409, detail="该路段已有生效中的封闭记录")

    closure = models.RoadClosure(
        pipe_id=pipe.id,
        start_node_id=body.start_node_id,
        end_node_id=body.end_node_id,
        reason=body.reason,
    )
    db.add(closure)
    db.flush()
    dispatch.replan_for_closure(db, closure)
    db.commit()
    db.refresh(closure)
    return closure


@router.post("/road-closures/{closure_id}/resolve", response_model=schemas.RoadClosureOut)
def resolve_closure(closure_id: int, db: Session = Depends(get_db)):
    closure = db.get(models.RoadClosure, closure_id)
    if closure is None:
        raise HTTPException(status_code=404, detail="closure not found")
    closure.active = False
    closure.resolved_at = datetime.utcnow()
    # replan once more so stranded orders can be picked up
    dispatch.replan_for_closure(db, closure)
    db.commit()
    db.refresh(closure)
    return closure


@router.get("/shortages", response_model=list[schemas.ShortageOut])
def list_shortages(open_only: bool = True, db: Session = Depends(get_db)):
    q = db.query(models.MaterialShortage)
    if open_only:
        q = q.filter(models.MaterialShortage.resolved.is_(False))
    return q.order_by(models.MaterialShortage.id.desc()).all()


@router.get("/notifications", response_model=list[schemas.NotificationOut])
def list_notifications(incident_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(models.Notification)
    if incident_id is not None:
        q = q.filter(models.Notification.incident_id == incident_id)
    return q.order_by(models.Notification.id.desc()).limit(200).all()
