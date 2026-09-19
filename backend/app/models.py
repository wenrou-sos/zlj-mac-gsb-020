"""SQLAlchemy ORM models for the water-grid emergency repair platform."""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base

# --- Status constants -------------------------------------------------------

INCIDENT_REPORTED = "reported"
INCIDENT_DISPATCHED = "dispatched"
INCIDENT_REPAIRING = "repairing"
INCIDENT_REPAIRED = "repaired"
INCIDENT_CLOSED = "closed"

WO_PLANNED = "planned"
WO_EN_ROUTE = "en_route"
WO_ON_SITE = "on_site"
WO_REPAIRING = "repairing"
WO_COMPLETED = "completed"
WO_REASSIGNED = "reassigned"
WO_DELAYED_MATERIAL = "delayed_material"

TEAM_IDLE = "idle"
TEAM_ASSIGNED = "assigned"
TEAM_ON_SITE = "on_site"

NODE_JUNCTION = "junction"
NODE_VALVE = "valve"
NODE_SOURCE = "source"


class NetworkNode(Base):
    __tablename__ = "network_nodes"

    id = Column(Integer, primary_key=True)
    code = Column(String(32), unique=True, nullable=False, index=True)
    type = Column(String(16), nullable=False, default=NODE_JUNCTION)  # junction/valve/source
    name = Column(String(128), nullable=True)
    x = Column(Float, nullable=False, default=0.0)  # schematic map coordinate
    y = Column(Float, nullable=False, default=0.0)
    is_open = Column(Boolean, nullable=False, default=True)  # valve state


class Pipe(Base):
    __tablename__ = "pipes"

    id = Column(Integer, primary_key=True)
    code = Column(String(32), unique=True, nullable=False, index=True)
    start_node_id = Column(Integer, ForeignKey("network_nodes.id"), nullable=False)
    end_node_id = Column(Integer, ForeignKey("network_nodes.id"), nullable=False)
    length_m = Column(Float, nullable=False, default=100.0)
    diameter_mm = Column(Integer, nullable=False, default=300)
    material = Column(String(32), nullable=False, default="ductile_iron")


class Consumer(Base):
    __tablename__ = "consumers"

    id = Column(Integer, primary_key=True)
    code = Column(String(32), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    category = Column(String(32), nullable=False, default="residential")  # residential/commercial/hospital/school
    node_id = Column(Integer, ForeignKey("network_nodes.id"), nullable=False)
    residents = Column(Integer, nullable=False, default=100)


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True)
    title = Column(String(128), nullable=False)
    pipe_id = Column(Integer, ForeignKey("pipes.id"), nullable=True)
    location_desc = Column(String(256), nullable=True)
    x = Column(Float, nullable=True)
    y = Column(Float, nullable=True)
    severity = Column(String(16), nullable=False, default="medium")  # low/medium/high
    description = Column(Text, nullable=True)
    reporter = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False, default=INCIDENT_REPORTED, index=True)
    affected_consumer_ids = Column(JSON, nullable=True)
    affected_residents = Column(Integer, nullable=False, default=0)
    isolation_valve_ids = Column(JSON, nullable=True)
    estimated_outage_minutes = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    work_orders = relationship("WorkOrder", back_populates="incident")
    pipe = relationship("Pipe")


class RepairTeam(Base):
    __tablename__ = "repair_teams"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), unique=True, nullable=False)
    base_node_id = Column(Integer, ForeignKey("network_nodes.id"), nullable=True)
    x = Column(Float, nullable=False, default=0.0)
    y = Column(Float, nullable=False, default=0.0)
    members = Column(Integer, nullable=False, default=4)
    skill_level = Column(Integer, nullable=False, default=2)  # 1..3
    status = Column(String(16), nullable=False, default=TEAM_IDLE, index=True)
    current_work_order_id = Column(
        Integer, ForeignKey("work_orders.id", use_alter=True), nullable=True
    )


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True)
    code = Column(String(32), unique=True, nullable=False)
    name = Column(String(64), nullable=False)
    unit = Column(String(16), nullable=False)
    stock = Column(Float, nullable=False, default=0.0)
    safety_stock = Column(Float, nullable=False, default=0.0)


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("repair_teams.id"), nullable=True)
    status = Column(String(32), nullable=False, default=WO_PLANNED, index=True)
    plan_summary = Column(Text, nullable=True)
    material_demand = Column(JSON, nullable=True)   # {material_code: qty}
    route_node_ids = Column(JSON, nullable=True)    # dispatch route
    route_distance_m = Column(Float, nullable=False, default=0.0)
    eta_minutes = Column(Integer, nullable=False, default=0)
    repair_minutes = Column(Integer, nullable=False, default=0)
    water_off = Column(Boolean, nullable=False, default=False)
    diverted = Column(Boolean, nullable=False, default=False)  # re-planned due to disruption
    replan_reason = Column(String(256), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    incident = relationship("Incident", back_populates="work_orders")
    team = relationship("RepairTeam", foreign_keys=[team_id])
    events = relationship(
        "WorkOrderEvent", back_populates="work_order", order_by="WorkOrderEvent.id"
    )


class WorkOrderEvent(Base):
    __tablename__ = "work_order_events"

    id = Column(Integer, primary_key=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=False)
    type = Column(String(32), nullable=False)  # status_change/road_closure/material/comment
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    work_order = relationship("WorkOrder", back_populates="events")


class RoadClosure(Base):
    __tablename__ = "road_closures"

    id = Column(Integer, primary_key=True)
    pipe_id = Column(Integer, ForeignKey("pipes.id"), nullable=True)
    start_node_id = Column(Integer, ForeignKey("network_nodes.id"), nullable=False)
    end_node_id = Column(Integer, ForeignKey("network_nodes.id"), nullable=False)
    reason = Column(String(256), nullable=False)
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class MaterialShortage(Base):
    __tablename__ = "material_shortages"

    id = Column(Integer, primary_key=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=True)
    material_code = Column(String(32), nullable=False)
    required_qty = Column(Float, nullable=False)
    available_qty = Column(Float, nullable=False)
    resolved = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=True)
    scope = Column(String(16), nullable=False, default="users")  # users/dispatch/public
    channel = Column(String(16), nullable=False, default="sms")  # sms/app/broadcast
    title = Column(String(128), nullable=False)
    message = Column(Text, nullable=False)
    affected_consumer_ids = Column(JSON, nullable=True)
    affected_residents = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
