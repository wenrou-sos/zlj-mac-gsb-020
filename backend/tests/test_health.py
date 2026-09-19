"""Startup / smoke tests: the service must boot, seed data and serve APIs."""
from fastapi.testclient import TestClient

from app import models
from app.main import app


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_openapi_available(client: TestClient):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    for p in [
        "/health", "/incidents", "/network/pipes",
        "/work-orders", "/road-closures", "/notifications", "/stats",
    ]:
        assert p in paths


def test_demo_data_seeded(client: TestClient):
    assert len(client.get("/network/nodes").json()) >= 10
    assert len(client.get("/network/pipes").json()) >= 9
    assert len(client.get("/network/consumers").json()) >= 9
    assert len(client.get("/teams").json()) == 3
    assert len(client.get("/materials").json()) >= 7


def test_stats_payload(client: TestClient):
    r = client.get("/stats")
    assert r.status_code == 200
    body = r.json()
    for key in ("open_incidents", "active_work_orders", "affected_residents",
                "teams_busy", "open_road_closures", "pending_shortages"):
        assert key in body
