from datetime import datetime

from pydantic import BaseModel, Field


# ---------- Zone ----------
class ZoneOut(BaseModel):
    id: int
    name: str
    district: str
    polygon: str
    centroid_x: float
    centroid_y: float
    users_count: int

    model_config = {"from_attributes": True}


# ---------- User ----------
class UserOut(BaseModel):
    id: int
    name: str
    phone: str
    address: str
    zone_id: int
    priority: bool
    location_x: float
    location_y: float

    model_config = {"from_attributes": True}


# ---------- Valve / Pipe ----------
class ValveOut(BaseModel):
    id: int
    code: str
    name: str
    location_x: float
    location_y: float
    is_open: bool
    diameter_mm: int

    model_config = {"from_attributes": True}


class PipeOut(BaseModel):
    id: int
    code: str
    from_x: float
    from_y: float
    to_x: float
    to_y: float
    diameter_mm: int
    material: str

    model_config = {"from_attributes": True}


# ---------- Team ----------
class TeamOut(BaseModel):
    id: int
    name: str
    leader: str
    phone: str
    home_x: float
    home_y: float
    location_x: float
    location_y: float
    status: str
    skills: str

    model_config = {"from_attributes": True}


# ---------- Material ----------
class MaterialOut(BaseModel):
    id: int
    code: str
    name: str
    unit: str
    stock: float
    safety_stock: float

    model_config = {"from_attributes": True}


class MaterialRestock(BaseModel):
    quantity: float = Field(gt=0)
    reason: str = "紧急调拨"


# ---------- Event ----------
class EventCreate(BaseModel):
    title: str
    description: str = ""
    reporter: str = "市民热线"
    reporter_phone: str = ""
    location_x: float
    location_y: float
    address: str = ""
    severity: str = "minor"
    pipe_diameter_mm: int = 200


class EventOut(BaseModel):
    id: int
    code: str
    title: str
    description: str
    reporter: str
    reporter_phone: str
    location_x: float
    location_y: float
    address: str
    severity: str
    pipe_diameter_mm: int
    status: str
    estimated_restore_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ImpactReport(BaseModel):
    event_id: int
    severity: str
    affected_zones: list[ZoneOut]
    affected_users: list[UserOut]
    affected_users_count: int
    priority_users_count: int
    valves_to_close: list[ValveOut]
    estimated_restore_at: datetime | None
    estimated_repair_minutes: int


# ---------- Dispatch ----------
class DispatchRequest(BaseModel):
    event_id: int


class CandidateTeam(BaseModel):
    team_id: int
    name: str
    status: str
    distance: float
    eta_minutes: int
    route_detour: bool
    feasible: bool
    reason: str = ""


class DispatchResult(BaseModel):
    work_order_id: int
    work_order_code: str
    team_id: int
    team_name: str
    eta_minutes: int
    route_detour: bool
    material_ready: bool
    shortages: list[dict]
    estimated_restore_at: datetime | None
    affected_users_count: int
    candidates: list[CandidateTeam]


# ---------- Work order / progress ----------
class ProgressAction(BaseModel):
    action: str
    note: str = ""


class ProgressLogOut(BaseModel):
    id: int
    action: str
    note: str
    progress_pct: int
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkOrderOut(BaseModel):
    id: int
    code: str
    event_id: int
    team_id: int
    status: str
    planned_eta_minutes: int
    route_detour: bool
    material_ready: bool
    shortage_note: str
    notes: str
    progress_pct: int
    assigned_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class WorkOrderDetail(WorkOrderOut):
    team: TeamOut | None = None
    logs: list[ProgressLogOut] = []


# ---------- Road closure ----------
class ClosureCreate(BaseModel):
    reason: str = "道路施工"
    from_x: float
    from_y: float
    to_x: float
    to_y: float


class ClosureOut(BaseModel):
    id: int
    code: str
    reason: str
    status: str
    from_x: float
    from_y: float
    to_x: float
    to_y: float
    created_at: datetime

    model_config = {"from_attributes": True}


class ReplanResult(BaseModel):
    closure_id: int
    adjusted_orders: list[dict]
    notified_users_count: int


# ---------- Notification ----------
class NotificationOut(BaseModel):
    id: int
    event_id: int
    user_id: int
    kind: str
    channel: str
    title: str
    content: str
    sent: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- Dashboard ----------
class DashboardStats(BaseModel):
    active_events: int
    open_work_orders: int
    available_teams: int
    total_teams: int
    affected_users_now: int
    low_stock_materials: list[MaterialOut]
    active_closures: int
    events_by_severity: dict[str, int]
    events_by_status: dict[str, int]


class FullMap(BaseModel):
    zones: list[ZoneOut]
    users: list[UserOut]
    valves: list[ValveOut]
    pipes: list[PipeOut]
    teams: list[TeamOut]
    events: list[EventOut]
    closures: list[ClosureOut]
