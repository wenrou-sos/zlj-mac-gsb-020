import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Column,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .database import Base


def gen_code(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


class Severity(str, enum.Enum):
    minor = "minor"
    moderate = "moderate"
    major = "major"
    critical = "critical"


class EventStatus(str, enum.Enum):
    reported = "reported"
    analyzed = "analyzed"
    dispatched = "dispatched"
    repairing = "repairing"
    restored = "restored"
    closed = "closed"


class TeamStatus(str, enum.Enum):
    available = "available"
    enroute = "enroute"
    onsite = "onsite"
    blocked_material = "blocked_material"
    blocked_road = "blocked_road"
    repairing = "repairing"
    offduty = "offduty"


class WorkOrderStatus(str, enum.Enum):
    assigned = "assigned"
    enroute = "enroute"
    valves_closed = "valves_closed"
    repairing = "repairing"
    blocked_material = "blocked_material"
    blocked_road = "blocked_road"
    pressure_testing = "pressure_testing"
    valves_reopened = "valves_reopened"
    completed = "completed"
    cancelled = "cancelled"


class ClosureStatus(str, enum.Enum):
    active = "active"
    resolved = "resolved"


event_zone = Table(
    "event_zone",
    Base.metadata,
    Column("event_id", Integer, ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
    Column("zone_id", Integer, ForeignKey("zones.id", ondelete="CASCADE"), primary_key=True),
)

valve_zone = Table(
    "valve_zone",
    Base.metadata,
    Column("valve_id", Integer, ForeignKey("valves.id", ondelete="CASCADE"), primary_key=True),
    Column("zone_id", Integer, ForeignKey("zones.id", ondelete="CASCADE"), primary_key=True),
)


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    district: Mapped[str] = mapped_column(String(100), default="")
    polygon: Mapped[str] = mapped_column(Text, default="")  # "x1,y1;x2,y2;..."
    centroid_x: Mapped[float] = mapped_column(Float, default=0)
    centroid_y: Mapped[float] = mapped_column(Float, default=0)
    users_count: Mapped[int] = mapped_column(Integer, default=0)

    valves: Mapped[list["Valve"]] = relationship(secondary=valve_zone, back_populates="zones")
    users: Mapped[list["WaterUser"]] = relationship(back_populates="zone")
    events: Mapped[list["Event"]] = relationship(secondary=event_zone, back_populates="affected_zones")


class WaterUser(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(30), default="")
    address: Mapped[str] = mapped_column(String(200), default="")
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"))
    priority: Mapped[bool] = mapped_column(Boolean, default=False)  # hospital/school etc.
    location_x: Mapped[float] = mapped_column(Float, default=0)
    location_y: Mapped[float] = mapped_column(Float, default=0)

    zone: Mapped[Zone] = relationship(back_populates="users")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user")


class Valve(Base):
    __tablename__ = "valves"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(100), default="")
    location_x: Mapped[float] = mapped_column(Float)
    location_y: Mapped[float] = mapped_column(Float)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    diameter_mm: Mapped[int] = mapped_column(Integer, default=300)

    zones: Mapped[list[Zone]] = relationship(secondary=valve_zone, back_populates="valves")
    actions: Mapped[list["ValveAction"]] = relationship(back_populates="valve")


class Pipe(Base):
    __tablename__ = "pipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    from_x: Mapped[float] = mapped_column(Float)
    from_y: Mapped[float] = mapped_column(Float)
    to_x: Mapped[float] = mapped_column(Float)
    to_y: Mapped[float] = mapped_column(Float)
    diameter_mm: Mapped[int] = mapped_column(Integer, default=300)
    material: Mapped[str] = mapped_column(String(30), default="ductile_iron")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    leader: Mapped[str] = mapped_column(String(100), default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    home_x: Mapped[float] = mapped_column(Float, default=0)
    home_y: Mapped[float] = mapped_column(Float, default=0)
    location_x: Mapped[float] = mapped_column(Float, default=0)
    location_y: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[TeamStatus] = mapped_column(Enum(TeamStatus), default=TeamStatus.available)
    skills: Mapped[str] = mapped_column(String(200), default="")  # comma separated, e.g. "welding,pump"

    work_orders: Mapped[list["WorkOrder"]] = relationship(back_populates="team")


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    unit: Mapped[str] = mapped_column(String(20), default="个")
    stock: Mapped[float] = mapped_column(Float, default=0)
    safety_stock: Mapped[float] = mapped_column(Float, default=0)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, default=lambda: gen_code("EVT"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    reporter: Mapped[str] = mapped_column(String(100), default="市民热线")
    reporter_phone: Mapped[str] = mapped_column(String(30), default="")
    location_x: Mapped[float] = mapped_column(Float)
    location_y: Mapped[float] = mapped_column(Float)
    address: Mapped[str] = mapped_column(String(200), default="")
    severity: Mapped[Severity] = mapped_column(Enum(Severity), default=Severity.minor)
    pipe_diameter_mm: Mapped[int] = mapped_column(Integer, default=200)
    status: Mapped[EventStatus] = mapped_column(Enum(EventStatus), default=EventStatus.reported)
    estimated_restore_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    affected_zones: Mapped[list[Zone]] = relationship(secondary=event_zone, back_populates="events")
    work_orders: Mapped[list["WorkOrder"]] = relationship(back_populates="event", cascade="all, delete-orphan")
    valve_actions: Mapped[list["ValveAction"]] = relationship(back_populates="event", cascade="all, delete-orphan")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="event", cascade="all, delete-orphan")


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, default=lambda: gen_code("WO"))
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    status: Mapped[WorkOrderStatus] = mapped_column(Enum(WorkOrderStatus), default=WorkOrderStatus.assigned)
    planned_eta_minutes: Mapped[int] = mapped_column(Integer, default=30)
    route_detour: Mapped[bool] = mapped_column(Boolean, default=False)
    material_ready: Mapped[bool] = mapped_column(Boolean, default=True)
    shortage_note: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    event: Mapped[Event] = relationship(back_populates="work_orders")
    team: Mapped[Team] = relationship(back_populates="work_orders")
    logs: Mapped[list["ProgressLog"]] = relationship(back_populates="work_order", cascade="all, delete-orphan")
    reservations: Mapped[list["MaterialReservation"]] = relationship(
        back_populates="work_order", cascade="all, delete-orphan"
    )


class ProgressLog(Base):
    __tablename__ = "progress_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(40))
    note: Mapped[str] = mapped_column(Text, default="")
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    work_order: Mapped[WorkOrder] = relationship(back_populates="logs")


class MaterialReservation(Base):
    __tablename__ = "material_reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id", ondelete="CASCADE"))
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    quantity: Mapped[float] = mapped_column(Float, default=0)
    satisfied: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    work_order: Mapped[WorkOrder] = relationship(back_populates="reservations")
    material: Mapped[Material] = relationship()


class MaterialTransaction(Base):
    __tablename__ = "material_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    change: Mapped[float] = mapped_column(Float)  # negative consume / positive restock
    reason: Mapped[str] = mapped_column(String(200), default="")
    work_order_id: Mapped[int | None] = mapped_column(ForeignKey("work_orders.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    material: Mapped[Material] = relationship()


class RoadClosure(Base):
    __tablename__ = "road_closures"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, default=lambda: gen_code("RC"))
    reason: Mapped[str] = mapped_column(String(200), default="道路施工")
    status: Mapped[ClosureStatus] = mapped_column(Enum(ClosureStatus), default=ClosureStatus.active)
    from_x: Mapped[float] = mapped_column(Float)
    from_y: Mapped[float] = mapped_column(Float)
    to_x: Mapped[float] = mapped_column(Float)
    to_y: Mapped[float] = mapped_column(Float)
    radius: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ValveAction(Base):
    __tablename__ = "valve_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    valve_id: Mapped[int] = mapped_column(ForeignKey("valves.id"))
    action: Mapped[str] = mapped_column(String(10))  # close / reopen
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)

    event: Mapped[Event] = relationship(back_populates="valve_actions")
    valve: Mapped[Valve] = relationship(back_populates="actions")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("event_id", "user_id", "kind", name="uq_notification_event_user_kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(30))  # shutdown / delay_material / detour / restored
    channel: Mapped[str] = mapped_column(String(20), default="sms")
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    sent: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event: Mapped[Event] = relationship(back_populates="notifications")
    user: Mapped[WaterUser] = relationship(back_populates="notifications")
