from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ClosureStatus, RoadClosure
from ..schemas import ClosureCreate, ClosureOut, ReplanResult
from ..services.progress import apply_closure_replan, resolve_closure

router = APIRouter(prefix="/api/closures", tags=["road-closures"])


@router.get("", response_model=list[ClosureOut])
def list_closures(db: Session = Depends(get_db)):
    return list(db.scalars(select(RoadClosure).order_by(RoadClosure.created_at.desc())).all())


@router.post("", response_model=ReplanResult, status_code=201)
def create_closure(payload: ClosureCreate, db: Session = Depends(get_db)):
    """Register a road closure and automatically replan affected en-route orders."""
    closure = RoadClosure(
        reason=payload.reason,
        from_x=payload.from_x,
        from_y=payload.from_y,
        to_x=payload.to_x,
        to_y=payload.to_y,
        status=ClosureStatus.active,
    )
    db.add(closure)
    db.commit()
    db.refresh(closure)
    return apply_closure_replan(db, closure)


@router.post("/{closure_id}/resolve")
def resolve(closure_id: int, db: Session = Depends(get_db)):
    closure = db.get(RoadClosure, closure_id)
    if not closure:
        raise HTTPException(404, "封路记录不存在")
    return resolve_closure(db, closure)
