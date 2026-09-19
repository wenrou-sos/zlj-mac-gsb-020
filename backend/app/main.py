from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, SessionLocal, engine
from .routers import closures, dispatch, events, materials, notifications, resources, work_orders
from .seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    if settings.seed_on_startup:
        db = SessionLocal()
        try:
            seed(db)
        finally:
            db.close()
    yield


app = FastAPI(
    title="城市供水管网抢修管理平台",
    description="漏损事件上报 · 影响区域分析 · 抢修派工 · 停复水进度跟踪 · 道路封闭/物料不足自动重规划",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events.router)
app.include_router(dispatch.router)
app.include_router(work_orders.router)
app.include_router(closures.router)
app.include_router(materials.router)
app.include_router(notifications.router)
app.include_router(resources.router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "water-grid-repair"}


@app.get("/", tags=["system"])
def root():
    return {
        "service": "城市供水管网抢修管理平台 API",
        "docs": "/docs",
        "health": "/health",
    }
