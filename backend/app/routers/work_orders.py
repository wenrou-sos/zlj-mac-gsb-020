from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services import dispatch

router = APIRouter(tags=["work-orders"])


@router.get("/work-orders", response_model=list[schemas.WorkOrderOut])
def list_work_orders(db: Session = Depends(get_db)):
    return (
        db.query(models.WorkOrder)
        .order_by(models.WorkOrder.id.desc())
        .all()
    )


@router.get("/work-orders/{wo_id}", response_model=schemas.WorkOrderOut)
def get_work_order(wo_id: int, db: Session = Depends(get_db)):
    wo = db.get(models.WorkOrder, wo_id)
    if wo is None:
        raise HTTPException(status_code=404, detail="work order not found")
    return wo


@router.post("/work-orders/{wo_id}/advance", response_model=schemas.WorkOrderOut)
def advance(wo_id: int, body: schemas.AdvanceBody | None = None, db: Session = Depends(get_db)):
    """Progress: en_route -> on_site (关阀停水) -> repairing -> complete via /complete."""
    wo = db.get(models.WorkOrder, wo_id)
    if wo is None:
        raise HTTPException(status_code=404, detail="work order not found")
    note = body.note if body else None
    dispatch.advance_work_order(db, wo, note)
    db.commit()
    db.refresh(wo)
    return wo


@router.post("/work-orders/{wo_id}/complete", response_model=schemas.WorkOrderOut)
def complete(wo_id: int, db: Session = Depends(get_db)):
    """维修完成，开阀复水。"""
    wo = db.get(models.WorkOrder, wo_id)
    if wo is None:
        raise HTTPException(status_code=404, detail="work order not found")
    if wo.status in (models.WO_COMPLETED, models.WO_REASSIGNED):
        raise HTTPException(status_code=409, detail="工单已结束")
    dispatch.complete_work_order(db, wo)
    db.commit()
    db.refresh(wo)
    return wo


@router.post("/work-orders/{wo_id}/shortage", response_model=schemas.ShortageOut, status_code=201)
def report_shortage(wo_id: int, body: schemas.ShortageCreate, db: Session = Depends(get_db)):
    """现场上报物料不足，自动调整复水计划并通知受影响用户。"""
    wo = db.get(models.WorkOrder, wo_id)
    if wo is None:
        raise HTTPException(status_code=404, detail="work order not found")
    sh = dispatch.report_material_shortage(db, wo, body.material_code, body.required_qty)
    db.commit()
    db.refresh(sh)
    return sh


@router.get("/teams", response_model=list[schemas.TeamOut])
def list_teams(db: Session = Depends(get_db)):
    return db.query(models.RepairTeam).order_by(models.RepairTeam.id).all()


@router.get("/materials", response_model=list[schemas.MaterialOut])
def list_materials(db: Session = Depends(get_db)):
    return db.query(models.Material).order_by(models.Material.id).all()


@router.post("/materials/{code}/restock", response_model=schemas.MaterialOut)
def restock(code: str, body: schemas.MaterialRestock, db: Session = Depends(get_db)):
    """物料到货入库，并自动恢复所有等待该物料的工单。"""
    mat = db.query(models.Material).filter(models.Material.code == code).first()
    if mat is None:
        raise HTTPException(status_code=404, detail="material not found")
    dispatch.restock_and_retry(db, code, body.qty)
    db.commit()
    db.refresh(mat)
    return mat
