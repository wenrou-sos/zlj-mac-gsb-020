def _report_and_dispatch(client, severity="major", x=15, y=30, diameter=600):
    resp = client.post(
        "/api/events",
        json={
            "title": "爆管",
            "location_x": x,
            "location_y": y,
            "address": "测试大道1号",
            "severity": severity,
            "pipe_diameter_mm": diameter,
        },
    )
    assert resp.status_code == 201, resp.text
    event = resp.json()
    client.post(f"/api/events/{event['id']}/analyze")
    result = client.post("/api/dispatch", json={"event_id": event["id"]})
    return event, result.json()


def test_material_shortage_blocks_and_resumes(client):
    event, dispatch = _report_and_dispatch(client, severity="critical", diameter=800)
    # Critical + DN800 cannot be satisfied from seed stock
    assert dispatch["material_ready"] is False
    assert dispatch["shortages"], "应当报告缺料明细"
    wo_id = dispatch["work_order_id"]
    assert client.get(f"/api/work-orders/{wo_id}").json()["material_ready"] is False

    # users are warned about the material-driven delay
    notes = client.get(f"/api/notifications?event_id={event['id']}").json()
    assert any(n["kind"] == "delay_material" for n in notes)

    # crew advances to the site then declares the shortage -> job blocked
    client.post(f"/api/work-orders/{wo_id}/progress", json={"action": "depart"})
    client.post(f"/api/work-orders/{wo_id}/progress", json={"action": "arrive"})
    client.post(f"/api/work-orders/{wo_id}/progress", json={"action": "close_valves"})
    client.post(
        f"/api/work-orders/{wo_id}/progress",
        json={"action": "report_material_shortage", "note": "DN800管材、焊条不足"},
    )
    wo = client.get(f"/api/work-orders/{wo_id}").json()
    assert wo["status"] == "blocked_material"

    # emergency procurement arrives: restock every missing material and allocate to the order
    materials = {m["code"]: m for m in client.get("/api/materials").json()}
    for shortage in dispatch["shortages"]:
        r = client.post(
            f"/api/materials/{materials[shortage['code']]['id']}/restock",
            json={"quantity": shortage["missing"] + 1, "reason": "紧急采购"},
        )
        assert r.status_code == 200
    recv = client.post(f"/api/materials/work-orders/{wo_id}/receive")
    assert recv.status_code == 200
    assert recv.json()["material_ready"] is True
    assert client.get(f"/api/work-orders/{wo_id}").json()["status"] == "repairing"


def test_road_closure_replans_active_order_and_notifies(client):
    # leak in zone 2 (40..60, 10..50); team 1 is based at (50,3)
    event, dispatch = _report_and_dispatch(client, severity="minor", x=50, y=30, diameter=200)
    wo_id = dispatch["work_order_id"]
    assert dispatch["route_detour"] is False

    # close the road that the team must cross (horizontal cut near y=18)
    resp = client.post(
        "/api/closures",
        json={"reason": "地铁施工道路封闭", "from_x": 42, "from_y": 18, "to_x": 58, "to_y": 18},
    )
    assert resp.status_code == 201, resp.text
    replan = resp.json()
    assert replan["adjusted_orders"], "工单路线应被判定为受阻"
    assert any(o["work_order_id"] == wo_id for o in replan["adjusted_orders"])
    assert replan["notified_users_count"] > 0

    wo = client.get(f"/api/work-orders/{wo_id}").json()
    assert wo["status"] == "blocked_road"
    assert wo["route_detour"] is True
    eta_before = client.get(f"/api/events/{event['id']}").json()["estimated_restore_at"]

    notes = client.get(f"/api/notifications?event_id={event['id']}").json()
    assert any(n["kind"] == "detour" for n in notes)

    # once the road reopens the order resumes automatically
    closure_id = replan["closure_id"]
    resolve = client.post(f"/api/closures/{closure_id}/resolve").json()
    assert wo["code"] in resolve["resumed_orders"]
    assert client.get(f"/api/work-orders/{wo_id}").json()["status"] == "enroute"
    eta_after = client.get(f"/api/events/{event['id']}").json()["estimated_restore_at"]
    assert eta_after == eta_before  # reopening does not erase the delay already announced


def test_no_team_available(client):
    # 3 teams / 3 zones -> the fourth dispatch must be rejected
    for i, x in enumerate([10, 45, 80]):
        resp = client.post(
            "/api/events",
            json={"title": f"漏损{i}", "location_x": x, "location_y": 30, "severity": "minor",
                  "pipe_diameter_mm": 200},
        )
        event = resp.json()
        client.post(f"/api/events/{event['id']}/analyze")
        r = client.post("/api/dispatch", json={"event_id": event["id"]})
        assert r.status_code == 200, r.text
    resp = client.post(
        "/api/events",
        json={"title": "第四处", "location_x": 15, "location_y": 45, "severity": "minor",
              "pipe_diameter_mm": 200},
    )
    event = resp.json()
    r = client.post("/api/dispatch", json={"event_id": event["id"]})
    assert r.status_code == 409
    assert "空闲抢修队" in r.json()["detail"]
