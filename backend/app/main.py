"""FastAPI application entry point for the water-grid emergency repair platform."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models
from .config import settings
from .database import Base, SessionLocal, engine
from .routers import disruptions, incidents, network, work_orders
from .seed import seed_demo


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    if settings.SEED_ON_STARTUP:
        db = SessionLocal()
        try:
            seed_demo(db)
        finally:
            db.close()
    yield


app = FastAPI(
    title="城市供水管网抢修管理平台",
    description="漏损上报 · 影响区域分析 · 抢修派工 · 停复水跟踪 · 道路封闭/物料不足自动改单",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(network.router)
app.include_router(incidents.router)
app.include_router(work_orders.router)
app.include_router(disruptions.router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "water-grid-repair", "version": "1.0.0"}


@app.get("/stats", tags=["system"])
def stats():
    db = SessionLocal()
    try:
        active_wo_states = [
            models.WO_EN_ROUTE, models.WO_ON_SITE, models.WO_REPAIRING,
            models.WO_PLANNED, models.WO_DELAYED_MATERIAL,
        ]
        open_incident_states = [
            models.INCIDENT_REPORTED, models.INCIDENT_DISPATCHED, models.INCIDENT_REPAIRING,
        ]
        return {
            "open_incidents": db.query(models.Incident)
            .filter(models.Incident.status.in_(open_incident_states)).count(),
            "active_work_orders": db.query(models.WorkOrder)
            .filter(models.WorkOrder.status.in_(active_wo_states)).count(),
            "affected_residents": sum(
                r or 0 for (r,) in db.query(models.Incident.affected_residents)
                .filter(models.Incident.status.in_(open_incident_states)).all()
            ),
            "teams_busy": db.query(models.RepairTeam)
            .filter(models.RepairTeam.status != models.TEAM_IDLE).count(),
            "open_road_closures": db.query(models.RoadClosure)
            .filter(models.RoadClosure.active.is_(True)).count(),
            "pending_shortages": db.query(models.MaterialShortage)
            .filter(models.MaterialShortage.resolved.is_(False)).count(),
            "water_off_orders": db.query(models.WorkOrder)
            .filter(models.WorkOrder.water_off.is_(True),
                    models.WorkOrder.status != models.WO_COMPLETED).count(),
        }
    finally:
        db.close()
