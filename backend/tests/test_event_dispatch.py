def _create_event(client, severity="moderate", x=15, y=30, diameter=300):
    resp = client.post(
        "/api/events",
        json={
            "title": f"{severity} 管网漏损",
            "description": "测试漏点",
            "reporter": "巡检员",
            "location_x": x,
            "location_y": y,
            "address": "滨江路测试点",
            "severity": severity,
            "pipe_diameter_mm": diameter,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_report_and_impact_analysis(client):
    event = _create_event(client, severity="critical", x=15, y=30)
    report = client.post(f"/api/events/{event['id']}/analyze").json()

    # critical leaks isolate the home zone plus neighbouring zones
    assert len(report["affected_zones"]) == 3
    assert report["affected_users_count"] == 30
    assert report["priority_users_count"] == 3
    assert len(report["valves_to_close"]) >= 5
    assert report["estimated_restore_at"] is not None

    status = client.get(f"/api/events/{event['id']}").json()["status"]
    assert status == "analyzed"


def test_full_dispatch_to_restoration_flow(client):
    event = _create_event(client, severity="minor", x=15, y=30)
    client.post(f"/api/events/{event['id']}/analyze")

    result = client.post("/api/dispatch", json={"event_id": event["id"]})
    assert result.status_code == 200, result.text
    data = result.json()
    wo_id = data["work_order_id"]
    assert data["material_ready"] is True
    assert data["affected_users_count"] == 10
    assert data["team_name"]  # nearest team chosen
    # shutdown SMS must have been queued for every affected user
    notes = client.get(f"/api/notifications?event_id={event['id']}").json()
    assert len([n for n in notes if n["kind"] == "shutdown"]) == 10

    # drive the lifecycle
    for action in ["depart", "arrive", "close_valves", "start_repair", "pressure_test", "reopen_valves", "complete"]:
        resp = client.post(f"/api/work-orders/{wo_id}/progress", json={"action": action})
        assert resp.status_code == 200, (action, resp.text)

    order = client.get(f"/api/work-orders/{wo_id}").json()
    assert order["status"] == "completed"
    assert order["progress_pct"] == 100

    valves = client.get("/api/valves").json()
    # all valves reopened after restoration
    assert all(v["is_open"] for v in valves)

    notes = client.get(f"/api/notifications?event_id={event['id']}").json()
    assert any(n["kind"] == "restored" for n in notes)


def test_cannot_dispatch_twice(client):
    event = _create_event(client, severity="minor", x=15, y=30)
    client.post(f"/api/dispatch", json={"event_id": event["id"]})
    resp = client.post("/api/dispatch", json={"event_id": event["id"]})
    assert resp.status_code == 409


def test_invalid_progress_transition_rejected(client):
    event = _create_event(client, severity="minor", x=15, y=30)
    wo_id = client.post("/api/dispatch", json={"event_id": event["id"]}).json()["work_order_id"]
    # cannot run pressure test right after assignment
    resp = client.post(f"/api/work-orders/{wo_id}/progress", json={"action": "pressure_test"})
    assert resp.status_code == 409
