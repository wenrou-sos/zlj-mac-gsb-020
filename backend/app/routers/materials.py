from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Material, MaterialTransaction, WorkOrder
from ..schemas import MaterialOut, MaterialRestock
from ..services.progress import receive_materials

router = APIRouter(prefix="/api/materials", tags=["materials"])


@router.get("", response_model=list[MaterialOut])
def list_materials(db: Session = Depends(get_db)):
    return list(db.scalars(select(Material).order_by(Material.id)).all())


@router.post("/{material_id}/restock", response_model=MaterialOut)
def restock(material_id: int, payload: MaterialRestock, db: Session = Depends(get_db)):
    mat = db.get(Material, material_id)
    if not mat:
        raise HTTPException(404, "物料不存在")
    mat.stock += payload.quantity
    db.add(
        MaterialTransaction(material_id=mat.id, change=payload.quantity, reason=payload.reason)
    )
    db.commit()
    db.refresh(mat)
    return mat


@router.post("/work-orders/{order_id}/receive")
def receive_order_materials(order_id: int, db: Session = Depends(get_db)):
    """Allocate incoming stock to a material-blocked work order and resume it."""
    order = db.get(WorkOrder, order_id)
    if not order:
        raise HTTPException(404, "工单不存在")
    order = receive_materials(db, order)
    db.commit()
    db.refresh(order)
    return {
        "work_order_id": order.id,
        "status": order.status.value,
        "material_ready": order.material_ready,
        "shortage_note": order.shortage_note,
    }
