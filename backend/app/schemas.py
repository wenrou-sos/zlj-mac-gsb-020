"""Pydantic request/response schemas."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# Network -------------------------------------------------------------------

class NodeOut(ORMModel):
    id: int
    code: str
    type: str
    name: Optional[str] = None
    x: float
    y: float
    is_open: bool


class PipeOut(ORMModel):
    id: int
    code: str
    start_node_id: int
    end_node_id: int
    length_m: float
    diameter_mm: int
    material: str


class ConsumerOut(ORMModel):
    id: int
    code: str
    name: str
    category: str
    node_id: int
    residents: int


# Incidents -----------------------------------------------------------------

class IncidentCreate(BaseModel):
    title: str
    pipe_id: Optional[int] = None
    location_desc: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    severity: str = "medium"
    description: Optional[str] = None
    reporter: Optional[str] = None


class IncidentOut(ORMModel):
    id: int
    title: str
    pipe_id: Optional[int]
    location_desc: Optional[str]
    x: Optional[float]
    y: Optional[float]
    severity: str
    description: Optional[str]
    reporter: Optional[str]
    status: str
    affected_consumer_ids: Optional[list[int]]
    affected_residents: int
    isolation_valve_ids: Optional[list[int]]
    estimated_outage_minutes: int
    created_at: datetime
    updated_at: datetime


class ImpactOut(BaseModel):
    isolation_valve_ids: list[int]
    affected_consumer_ids: list[int]
    affected_consumers: list[dict[str, Any]]
    affected_residents: int
    alternative_route_available: bool
    warnings: list[str]


# Teams / materials / work orders -------------------------------------------

class TeamOut(ORMModel):
    id: int
    name: str
    x: float
    y: float
    members: int
    skill_level: int
    status: str


class MaterialOut(ORMModel):
    id: int
    code: str
    name: str
    unit: str
    stock: float
    safety_stock: float


class MaterialRestock(BaseModel):
    qty: float


class EventOut(ORMModel):
    id: int
    type: str
    message: str
    created_at: datetime


class WorkOrderOut(ORMModel):
    id: int
    incident_id: int
    team_id: Optional[int]
    status: str
    plan_summary: Optional[str]
    material_demand: Optional[dict[str, float]]
    route_node_ids: Optional[list[int]]
    route_distance_m: float
    eta_minutes: int
    repair_minutes: int
    water_off: bool
    diverted: bool
    replan_reason: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    team: Optional[TeamOut] = None
    events: list[EventOut] = []


class AdvanceBody(BaseModel):
    note: Optional[str] = None


# Disruptions ----------------------------------------------------------------

class RoadClosureCreate(BaseModel):
    start_node_id: int
    end_node_id: int
    reason: str


class RoadClosureOut(ORMModel):
    id: int
    start_node_id: int
    end_node_id: int
    reason: str
    active: bool
    created_at: datetime
    resolved_at: Optional[datetime]


class ShortageCreate(BaseModel):
    material_code: str
    required_qty: float


class ShortageOut(ORMModel):
    id: int
    work_order_id: Optional[int]
    material_code: str
    required_qty: float
    available_qty: float
    resolved: bool
    created_at: datetime


class NotificationOut(ORMModel):
    id: int
    incident_id: Optional[int]
    work_order_id: Optional[int]
    scope: str
    channel: str
    title: str
    message: str
    affected_consumer_ids: Optional[list[int]]
    affected_residents: int
    created_at: datetime


class StatsOut(BaseModel):
    open_incidents: int
    active_work_orders: int
    affected_residents: int
    teams_busy: int
    open_road_closures: int
    pending_shortages: int
    water_off_orders: int
