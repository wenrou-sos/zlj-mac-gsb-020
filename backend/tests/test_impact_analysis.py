"""Impact-area analysis on the demo network."""
from fastapi.testclient import TestClient


def test_valve_boundary_leaf_branch(client: TestClient, pipe_by_code, node_by_code):
    # Break V5-J6: closing V5 isolates only the east block (J6 consumers).
    pipe = pipe_by_code("P-V5-6")
    data = client.get(f"/network/impact/pipe/{pipe.id}").json()

    assert data["isolation_valve_ids"] == [node_by_code("V5").id]
    assert set(data["affected_consumer_ids"]) == {7, 8, 9}
    assert data["affected_residents"] == 300
    assert data["alternative_route_available"] is False
    assert data["warnings"] == []


def test_loop_block_requires_two_valves(client: TestClient, pipe_by_code, node_by_code):
    # Break V1-J4: west block is linked to center block via the J4-J5 loop,
    # so BOTH V1 and V3 must be shut (180+160 + 220+240 = 800 residents).
    pipe = pipe_by_code("P-V1-4")
    data = client.get(f"/network/impact/pipe/{pipe.id}").json()

    assert set(data["isolation_valve_ids"]) == {
        node_by_code("V1").id, node_by_code("V3").id
    }
    assert set(data["affected_consumer_ids"]) == {1, 2, 3, 4, 5, 6}
    assert data["affected_residents"] == 800
    assert data["alternative_route_available"] is False


def test_trunk_break_warns_about_source_side(client: TestClient, pipe_by_code, node_by_code):
    # Main trunk J1-J2: the J1 side reaches the water plant with no valve,
    # so operators must depressurize at plant level; V3/V5 seal downstream.
    data = client.get(f"/network/impact/pipe/{pipe_by_code('P-1-2').id}").json()

    assert set(data["isolation_valve_ids"]) == {
        node_by_code("V3").id, node_by_code("V5").id
    }
    assert any("水厂" in w or "干管" in w for w in data["warnings"])
    assert set(data["affected_consumer_ids"]) == {7, 8, 9}
