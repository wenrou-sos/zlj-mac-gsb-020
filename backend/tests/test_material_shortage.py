"""Material-shortage handling: delays, cross-depot transfer and auto-resume."""
from fastapi.testclient import TestClient


def test_dispatch_with_insufficient_stock_delays_order(client: TestClient):
    # medium BOM needs 2x pipe_dn300; demo stock is exactly 2 for the first
    # order. Report two medium breaks so the second one lacks the pipe.
    pipes = {p["code"]: p for p in client.get("/network/pipes").json()}

    inc1 = client.post("/incidents", json={
        "title": "中心支线渗漏", "pipe_id": pipes["P-V3-5"]["id"], "severity": "medium",
    }).json()
    wo1 = client.post(f"/incidents/{inc1['id']}/dispatch").json()
    assert wo1["status"] != "delayed_material"

    inc2 = client.post("/incidents", json={
        "title": "东站支线渗漏", "pipe_id": pipes["P-V5-6"]["id"], "severity": "medium",
    }).json()
    wo2 = client.post(f"/incidents/{inc2['id']}/dispatch").json()
    assert wo2["status"] == "delayed_material"
    assert "pipe_dn300" in wo2["replan_reason"]

    # shortage row + user notice with impact scope
    shortages = client.get("/shortages", params={"open_only": True}).json()
    assert any(s["material_code"] == "pipe_dn300" and s["work_order_id"] == wo2["id"]
               for s in shortages)
    notes = client.get(f"/notifications?incident_id={inc2['id']}").json()
    assert any(n["title"] == "停水时间可能延长" and n["affected_residents"] == 300
               for n in notes)

    # emergency transfer arrives -> work order resumes automatically
    r = client.post("/materials/pipe_dn300/restock", json={"qty": 5})
    assert r.status_code == 200
    wo3 = client.get(f"/work-orders/{wo2['id']}").json()
    assert wo3["status"] == "en_route"
    assert wo3["replan_reason"] is None
    assert client.get("/shortages", params={"open_only": True}).json() == []
    notes = client.get(f"/notifications?incident_id={inc2['id']}").json()
    assert any(n["title"] == "物料到位：抢修恢复" for n in notes)


def test_onsite_shortage_report_after_repair_started(client: TestClient):
    pipes = {p["code"]: p for p in client.get("/network/pipes").json()}
    inc = client.post("/incidents", json={
        "title": "支线爆管", "pipe_id": pipes["P-V5-6"]["id"], "severity": "low",
    }).json()
    wo = client.post(f"/incidents/{inc['id']}/dispatch").json()
    wo = client.post(f"/work-orders/{wo['id']}/advance").json()  # on site, water off
    wo = client.post(f"/work-orders/{wo['id']}/advance").json()  # repairing
    assert wo["status"] == "repairing"

    # excavate, find a broken valve needs replacing but stock is held by others
    r = client.post(f"/work-orders/{wo['id']}/shortage", json={
        "material_code": "valve_dn300", "required_qty": 2,
    })
    assert r.status_code == 201
    wo = client.get(f"/work-orders/{wo['id']}").json()
    assert wo["status"] == "delayed_material"
    notes = client.get(f"/notifications?incident_id={inc['id']}").json()
    assert any("复水时间调整" in n["title"] for n in notes)

    # restock resumes from repairing (team already on site)
    client.post("/materials/valve_dn300/restock", json={"qty": 2})
    wo = client.get(f"/work-orders/{wo['id']}").json()
    assert wo["status"] == "repairing"
