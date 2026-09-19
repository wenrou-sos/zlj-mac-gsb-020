def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_seed_data_loaded(client):
    assert len(client.get("/api/zones").json()) == 3
    assert len(client.get("/api/teams").json()) == 3
    users = client.get("/api/users").json()
    assert len(users) == 30
    assert any(u["priority"] for u in users)  # hospital/school accounts
    assert len(client.get("/api/materials").json()) == 6


def test_dashboard_smoke(client):
    stats = client.get("/api/dashboard").json()
    assert stats["total_teams"] == 3
    assert stats["available_teams"] == 3
    assert stats["active_events"] == 0
