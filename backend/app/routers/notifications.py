from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Notification
from ..schemas import NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(event_id: int | None = None, limit: int = 200, db: Session = Depends(get_db)):
    stmt = select(Notification).order_by(Notification.created_at.desc()).limit(limit)
    if event_id is not None:
        stmt = stmt.where(Notification.event_id == event_id)
    return list(db.scalars(stmt).all())
