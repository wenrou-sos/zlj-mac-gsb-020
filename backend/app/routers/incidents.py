from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services import dispatch
from ..services.network import analyze_affected_area

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=list[schemas.IncidentOut])
def list_incidents(db: Session = Depends(get_db)):
    return db.query(models.Incident).order_by(models.Incident.id.desc()).all()


@router.post("", response_model=schemas.IncidentOut, status_code=201)
def create_incident(body: schemas.IncidentCreate, db: Session = Depends(get_db)):
    if body.pipe_id is None and (body.x is None or body.y is None):
        raise HTTPException(status_code=400, detail="pipe_id 或坐标(x,y)至少提供一项")

    incident = models.Incident(**body.model_dump())
    db.add(incident)
    db.flush()

    # 影响区域分析
    if incident.pipe_id:
        impact = analyze_affected_area(db, incident.pipe)
        incident.isolation_valve_ids = impact["isolation_valve_ids"]
        incident.affected_consumer_ids = impact["affected_consumer_ids"]
        incident.affected_residents = impact["affected_residents"]
        # attach warning lines into description for dispatchers
        if impact["warnings"]:
            incident.description = (incident.description or "") + "\n[分析告警] " + "；".join(impact["warnings"])

    db.commit()
    db.refresh(incident)
    return incident


@router.get("/{incident_id}", response_model=schemas.IncidentOut)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    inc = db.get(models.Incident, incident_id)
    if inc is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return inc


@router.get("/{incident_id}/impact", response_model=schemas.ImpactOut)
def incident_impact(incident_id: int, db: Session = Depends(get_db)):
    inc = db.get(models.Incident, incident_id)
    if inc is None or inc.pipe_id is None:
        raise HTTPException(status_code=404, detail="incident or pipe not found")
    return analyze_affected_area(db, inc.pipe)


@router.post("/{incident_id}/dispatch", response_model=schemas.WorkOrderOut, status_code=201)
def dispatch_incident(incident_id: int, db: Session = Depends(get_db)):
    inc = db.get(models.Incident, incident_id)
    if inc is None:
        raise HTTPException(status_code=404, detail="incident not found")
    if inc.status not in (models.INCIDENT_REPORTED,):
        raise HTTPException(status_code=409, detail="该事件已派工")
    wo = dispatch.dispatch(db, inc)
    db.commit()
    db.refresh(wo)
    return wo
