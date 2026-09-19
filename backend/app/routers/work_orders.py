from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import ProgressLog, WorkOrder
from ..schemas import ProgressAction, ProgressLogOut, WorkOrderDetail, WorkOrderOut
from ..services.progress import apply_action

router = APIRouter(prefix="/api/work-orders", tags=["work-orders"])


@router.get("", response_model=list[WorkOrderOut])
def list_work_orders(db: Session = Depends(get_db)):
    return list(db.scalars(select(WorkOrder).order_by(WorkOrder.assigned_at.desc())).all())


@router.get("/{order_id}", response_model=WorkOrderDetail)
def get_work_order(order_id: int, db: Session = Depends(get_db)):
    order = db.scalar(
        select(WorkOrder)
        .where(WorkOrder.id == order_id)
        .options(joinedload(WorkOrder.team), joinedload(WorkOrder.logs))
    )
    if not order:
        raise HTTPException(404, "工单不存在")
    return order


@router.post("/{order_id}/progress", response_model=WorkOrderDetail)
def post_progress(order_id: int, payload: ProgressAction, db: Session = Depends(get_db)):
    order = db.scalar(
        select(WorkOrder)
        .where(WorkOrder.id == order_id)
        .options(joinedload(WorkOrder.team), joinedload(WorkOrder.logs))
    )
    if not order:
        raise HTTPException(404, "工单不存在")
    try:
        order = apply_action(db, order, payload.action, payload.note)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

    pct = order.progress_pct
    label = {
        "depart": "出发",
        "arrive": "到场",
        "close_valves": "关阀停水",
        "start_repair": "开始修复",
        "repair_update": "修复推进",
        "pressure_test": "打压测试",
        "reopen_valves": "开阀复水",
        "complete": "完工",
        "report_material_shortage": "报告物料不足",
        "materials_received": "补料到货",
    }.get(payload.action, payload.action)
    db.add(
        ProgressLog(
            work_order_id=order.id,
            action=payload.action,
            note=payload.note or label,
            progress_pct=pct,
        )
    )
    db.commit()
    db.refresh(order)
    return order


@router.get("/{order_id}/logs", response_model=list[ProgressLogOut])
def get_logs(order_id: int, db: Session = Depends(get_db)):
    if not db.get(WorkOrder, order_id):
        raise HTTPException(404, "工单不存在")
    return list(
        db.scalars(
            select(ProgressLog).where(ProgressLog.work_order_id == order_id).order_by(ProgressLog.created_at)
        ).all()
    )
