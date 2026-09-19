"""Road-closure auto-replanning: detours, reassignment and user notices."""
from fastapi.testclient import TestClient


def _dispatch_on(client: TestClient, pipe_code: str, severity: str = "low"):
    pipes = {p["code"]: p for p in client.get("/network/pipes").json()}
    inc = client.post("/incidents", json={
        "title": f"{pipe_code} 漏损",
        "pipe_id": pipes[pipe_code]["id"],
        "severity": severity,
    }).json()
    wo = client.post(f"/incidents/{inc['id']}/dispatch").json()
    return inc, wo


def _close_road(client: TestClient, start_code: str, end_code: str, reason: str):
    nodes = {n["code"]: n for n in client.get("/network/nodes").json()}
    r = client.post("/road-closures", json={
        "start_node_id": nodes[start_code]["id"],
        "end_node_id": nodes[end_code]["id"],
        "reason": reason,
    })
    assert r.status_code == 201, r.text
    return r.json()


def test_closure_detour_reroutes_team(client: TestClient):
    # west-block break: 甲班 (based at J1) is closest, reaches via J1-V1
    inc, wo = _dispatch_on(client, "P-V1-4")
    assert wo["team_id"] == 1
    original_path = wo["route_node_ids"]

    # close J1-V1: 甲班 must detour J1->J2->V3->J5->J4->V1... wait J4 side,
    # i.e. via the loop J2-V3-J5-J4; work order is marked diverted
    closure = _close_road(client, "J1", "V1", "市政道路施工封闭")

    wo2 = client.get(f"/work-orders/{wo['id']}").json()
    assert wo2["diverted"] is True
    assert wo2["team_id"] == 1
    assert wo2["route_node_ids"] != original_path
    assert wo2["eta_minutes"] > wo["eta_minutes"]
    assert "道路封闭" in wo2["replan_reason"]

    events = [e["message"] for e in wo2["events"]]
    assert any("改道" in e for e in events)

    notes = client.get(f"/notifications?incident_id={inc['id']}").json()
    assert any("道路封闭" in n["title"] for n in notes)

    # stats reflect the closure
    assert client.get("/stats").json()["open_road_closures"] >= 1


def test_closure_cutting_team_off_triggers_reassignment(client: TestClient):
    # break on V1-J4: nearest is 甲班 at J1
    inc, wo = _dispatch_on(client, "P-V1-4")
    assert wo["team_id"] == 1

    # close every edge out of J1 (S-J1, J1-J2, J1-V1): 甲班 is cut off,
    # 乙班 (J2) takes over via J2-V3-J5-J4
    _close_road(client, "S", "J1", "路口塌方封闭")
    _close_road(client, "J1", "J2", "地铁施工封闭")
    _close_road(client, "J1", "V1", "匝道封闭")

    wo2 = client.get(f"/work-orders/{wo['id']}").json()
    assert wo2["team_id"] == 2
    assert wo2["status"] == "en_route"
    assert wo2["diverted"] is True
    assert "改派" in wo2["replan_reason"]

    # old team released, new team busy
    teams = {t["id"]: t for t in client.get("/teams").json()}
    assert teams[1]["status"] == "idle"
    assert teams[2]["status"] == "assigned"

    notes = client.get(f"/notifications?incident_id={inc['id']}").json()
    assert any("改派" in n["message"] for n in notes)


def test_resolve_closure_replans_stranded_order(client: TestClient):
    # seal the west block off from every team (J1 + both loop entries):
    # order stays unassigned until roads reopen
    _close_road(client, "S", "J1", "临时管制")
    _close_road(client, "J1", "J2", "临时管制")
    _close_road(client, "J1", "V1", "临时管制")
    _close_road(client, "J2", "V3", "临时管制")
    inc, wo = _dispatch_on(client, "P-V1-4")
    assert wo["team_id"] is None
    assert wo["status"] == "planned"

    closures = client.get("/road-closures", params={"active_only": True}).json()
    assert len(closures) == 4
    for c in closures:
        client.post(f"/road-closures/{c['id']}/resolve")

    wo2 = client.get(f"/work-orders/{wo['id']}").json()
    assert wo2["team_id"] == 2  # after reopening, 乙班 via J2-V3-J5 is closest
    assert wo2["status"] == "en_route"
