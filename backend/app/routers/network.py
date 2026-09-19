from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services.network import analyze_affected_area

router = APIRouter(prefix="/network", tags=["network"])


@router.get("/nodes", response_model=list[schemas.NodeOut])
def list_nodes(db: Session = Depends(get_db)):
    return db.query(models.NetworkNode).order_by(models.NetworkNode.id).all()


@router.get("/pipes", response_model=list[schemas.PipeOut])
def list_pipes(db: Session = Depends(get_db)):
    return db.query(models.Pipe).order_by(models.Pipe.id).all()


@router.get("/consumers", response_model=list[schemas.ConsumerOut])
def list_consumers(db: Session = Depends(get_db)):
    return db.query(models.Consumer).order_by(models.Consumer.id).all()


@router.get("/impact/pipe/{pipe_id}", response_model=schemas.ImpactOut)
def pipe_impact(pipe_id: int, db: Session = Depends(get_db)):
    pipe = db.get(models.Pipe, pipe_id)
    if pipe is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="pipe not found")
    return analyze_affected_area(db, pipe)
