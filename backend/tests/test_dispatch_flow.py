"""End-to-end: report -> impact analysis -> dispatch -> stop water -> repair -> restart."""
from fastapi.testclient import TestClient

from app import models


def _report_branch_incident(client: TestClient, pipe_code: str = "P-V5-6",
                            severity: str = "medium") -> dict:
    pipes = {p["code"]: p for p in client.get("/network/pipes").json()}
    pipe_id = pipes[pipe_code]["id"]
    r = client.post("/incidents", json={
        "title": f"{pipe_code} 爆管",
        "pipe_id": pipe_id,
        "severity": severity,
        "location_desc": "测试路段",
        "reporter": "巡检员小王",
    })
    assert r.status_code == 201, r.text
    inc = r.json()
    assert inc["status"] == "reported"
    assert inc["affected_residents"] == 300
    assert inc["isolation_valve_ids"]  # auto impact analysis ran
    return inc


def test_full_repair_lifecycle(client: TestClient):
    inc = _report_branch_incident(client)

    # dispatch: closest team is the east-zone team based at J3
    r = client.post(f"/incidents/{inc['id']}/dispatch")
    assert r.status_code == 201, r.text
    wo = r.json()
    assert wo["status"] == "en_route"
    assert wo["team_id"] == 3
    assert wo["route_node_ids"]
    assert wo["eta_minutes"] >= 1
    assert wo["water_off"] is False

    # user notification about dispatch with impact scope
    notes = client.get(f"/notifications?incident_id={inc['id']}").json()
    assert any(n["title"] == "抢修已派工" and n["affected_residents"] == 300 for n in notes)

    # arrive on site -> valves close, water off
    wo = client.post(f"/work-orders/{wo['id']}/advance").json()
    assert wo["status"] == "on_site"
    assert wo["water_off"] is True
    nodes = {n["code"]: n for n in client.get("/network/nodes").json()}
    assert nodes["V5"]["is_open"] is False
    assert any(n["title"] == "停水通知" for n in
               client.get(f"/notifications?incident_id={inc['id']}").json())

    # repairing
    wo = client.post(f"/work-orders/{wo['id']}/advance",
                     json={"note": "更换DN300管段"}).json()
    assert wo["status"] == "repairing"
    assert wo["started_at"] is not None

    # complete -> valves reopen, water restored
    wo = client.post(f"/work-orders/{wo['id']}/complete").json()
    assert wo["status"] == "completed"
    assert wo["water_off"] is False
    nodes = {n["code"]: n for n in client.get("/network/nodes").json()}
    assert nodes["V5"]["is_open"] is True
    inc = client.get(f"/incidents/{inc['id']}").json()
    assert inc["status"] == "repaired"
    notes = client.get(f"/notifications?incident_id={inc['id']}").json()
    assert any(n["title"] == "复水通知" for n in notes)

    # team released
    teams = {t["id"]: t for t in client.get("/teams").json()}
    assert teams[3]["status"] == "idle"


def test_cannot_dispatch_twice(client: TestClient):
    inc = _report_branch_incident(client)
    assert client.post(f"/incidents/{inc['id']}/dispatch").status_code == 201
    r = client.post(f"/incidents/{inc['id']}/dispatch")
    assert r.status_code == 409
