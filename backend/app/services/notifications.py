from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Event, Notification, WaterUser
from .impact import SEVERITY_LABEL


def _fmt_eta(eta) -> str:
    if eta is None:
        return "待定"
    return eta.strftime("%H:%M")


def notify_users(
    db: Session,
    event: Event,
    users: list[WaterUser],
    kind: str,
    title: str,
    content_template: str,
    extra_fields: dict | None = None,
) -> list[Notification]:
    """Create notifications, skipping duplicates (same event+user+kind)."""
    existing = {
        (n.user_id, n.kind)
        for n in db.scalars(select(Notification).where(Notification.event_id == event.id)).all()
    }
    created: list[Notification] = []
    sev = SEVERITY_LABEL.get(event.severity.value if hasattr(event.severity, "value") else event.severity, "")
    fields = {"severity": sev, **(extra_fields or {})}
    for user in users:
        if (user.id, kind) in existing:
            continue
        content = content_template.format(
            user=user.name,
            event=event.code,
            address=event.address or "事发点",
            eta=_fmt_eta(event.estimated_restore_at),
            **fields,
        )
        note = Notification(
            event_id=event.id,
            user_id=user.id,
            kind=kind,
            title=title,
            content=content,
        )
        db.add(note)
        created.append(note)
    return created


def shutdown_notification(db: Session, event: Event, users: list[WaterUser]) -> list[Notification]:
    return notify_users(
        db,
        event,
        users,
        kind="shutdown",
        title="停水通知",
        content_template=(
            "尊敬的{user}：因{address}供水管道{severity}漏损（工单{event}），"
            "您所在区域即将停水抢修，预计{eta}恢复供水，请提前储水。详询96333。"
        ),
    )


def material_delay_notification(db: Session, event: Event, users: list[WaterUser], detail: str) -> list[Notification]:
    return notify_users(
        db,
        event,
        users,
        kind="delay_material",
        title="抢修延时通知（物料）",
        content_template=(
            "尊敬的{user}：工单{event}因" + detail + "物料不足正在紧急调拨，"
            "预计{eta}恢复供水，给您带来不便敬请谅解。"
        ),
    )


def road_detour_notification(db: Session, event: Event, users: list[WaterUser], reason: str) -> list[Notification]:
    return notify_users(
        db,
        event,
        users,
        kind="detour",
        title="抢修延时通知（道路封闭）",
        content_template=(
            "尊敬的{user}：因{reason}，工单{event}抢修车辆需绕行，到场时间延后，"
            "预计{eta}恢复供水，敬请留意。"
        ),
        extra_fields={"reason": reason},
    )


def restored_notification(db: Session, event: Event, users: list[WaterUser]) -> list[Notification]:
    return notify_users(
        db,
        event,
        users,
        kind="restored",
        title="恢复供水通知",
        content_template="尊敬的{user}：工单{event}已抢修完成，您所在区域已恢复供水，请关注水质变化。",
    )
