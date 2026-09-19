"""Demo dataset: a small looped water network with a source, valves on every
branch, residential/commercial consumers, three repair teams and a warehouse.

Schematic layout (x,y are map coordinates, roughly 0..1000):

  S(0) ==== J1(1) ==== J2(2) ==== J3(3)
              ||         ||         ||
             V1(4)      V3(7)      V5(10)
              |          |          |
             J4(5)===J5(8)        J6(11)      (J4-J5 loop back to J2)
              |       |             |
            C1..C3   C4..C6       C7..C9
"""
from sqlalchemy.orm import Session

from . import models


def seed_demo(db: Session) -> bool:
    if db.query(models.NetworkNode).count() > 0:
        return False

    def node(code, ntype, x, y, name=None, is_open=True):
        n = models.NetworkNode(code=code, type=ntype, name=name or code, x=x, y=y, is_open=is_open)
        db.add(n)
        return n

    s = node("S", "source", 60, 260, "第一水厂")
    j1 = node("J1", "junction", 260, 260, "干管节点J1")
    j2 = node("J2", "junction", 500, 260, "干管节点J2")
    j3 = node("J3", "junction", 760, 260, "干管节点J3")
    v1 = node("V1", "valve", 260, 360, "西园支线阀V1")
    j4 = node("J4", "junction", 180, 460, "西园节点J4")
    v3 = node("V3", "valve", 500, 360, "中心支线阀V3")
    j5 = node("J5", "junction", 420, 460, "中心节点J5")
    v5 = node("V5", "valve", 760, 360, "东站支线阀V5")
    j6 = node("J6", "junction", 760, 460, "东站节点J6")
    db.flush()

    def pipe(code, a, b, length, diameter=300):
        db.add(models.Pipe(code=code, start_node_id=a.id, end_node_id=b.id,
                           length_m=length, diameter_mm=diameter))

    pipe("P-S-1", s, j1, 200, 600)
    pipe("P-1-2", j1, j2, 240, 500)
    pipe("P-2-3", j2, j3, 260, 500)
    pipe("P-1-V1", j1, v1, 100)
    pipe("P-V1-4", v1, j4, 100)
    pipe("P-2-V3", j2, v3, 100)
    pipe("P-V3-5", v3, j5, 110)
    pipe("P-4-5", j4, j5, 260)          # loop: alternative feed to center block
    pipe("P-3-V5", j3, v5, 100)
    pipe("P-V5-6", v5, j6, 100)
    db.flush()

    consumers = [
        ("U01", "西园小区1栋", "residential", j4, 180),
        ("U02", "西园小区2栋", "residential", j4, 160),
        ("U03", "西园社区医院", "hospital", j4, 0),
        ("U04", "中心花园A座", "residential", j5, 220),
        ("U05", "中心花园B座", "residential", j5, 240),
        ("U06", "市民中心", "government", j5, 0),
        ("U07", "东站商贸城", "commercial", j6, 0),
        ("U08", "东站宿舍", "residential", j6, 300),
        ("U09", "东站小学", "school", j6, 0),
    ]
    for code, name, cat, nd, residents in consumers:
        db.add(models.Consumer(code=code, name=name, category=cat,
                               node_id=nd.id, residents=residents))

    db.add_all([
        models.RepairTeam(name="甲班抢修队", base_node_id=j1.id, x=260, y=220,
                          members=5, skill_level=3),
        models.RepairTeam(name="乙班抢修队", base_node_id=j2.id, x=500, y=220,
                          members=4, skill_level=2),
        models.RepairTeam(name="东郊抢修队", base_node_id=j3.id, x=760, y=220,
                          members=4, skill_level=2),
    ])

    db.add_all([
        models.Material(code="pipe_dn100", name="DN100球墨铸铁管", unit="根", stock=10, safety_stock=4),
        models.Material(code="pipe_dn300", name="DN300球墨铸铁管", unit="根", stock=2, safety_stock=4),
        models.Material(code="pipe_dn500", name="DN500钢管", unit="根", stock=3, safety_stock=2),
        models.Material(code="coupler", name="快速接头", unit="个", stock=12, safety_stock=8),
        models.Material(code="seal", name="密封胶圈", unit="只", stock=40, safety_stock=20),
        models.Material(code="valve_dn300", name="DN300阀门", unit="台", stock=1, safety_stock=1),
        models.Material(code="pump", name="移动抽水泵", unit="台", stock=2, safety_stock=1),
    ])
    db.commit()
    return True
