"""Idempotent demo data: 3 zones on a 0..100 map, users, valves, teams, materials."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Material, Pipe, Team, TeamStatus, Valve, WaterUser, Zone

MATERIAL_CATALOG = [
    ("PIPE_SECTION", "DN300球墨铸铁管(6m/根)", "根", 1.0, 2.0),
    ("PIPE_CLAMP", "管道抢修哈夫节", "个", 20.0, 6.0),
    ("RUBBER_SEAL", "橡胶密封圈", "个", 60.0, 20.0),
    ("BOLT_SET", "高强度螺栓组", "套", 120.0, 40.0),
    ("WELDING_ROD", "焊条", "包", 30.0, 10.0),
    ("WATER_PUMP", "移动抽水泵", "台", 3.0, 1.0),
]

# x0,y0 top-left; each zone 30 wide x 50 tall with a 5-unit gap between blocks
ZONE_DEFS = [
    ("滨江区", "江城区", 5, 10),
    ("望湖区", "江城区", 40, 10),
    ("青枫区", "东城区", 75, 10),
]

USER_SURNAMES = list("王李张刘陈杨黄赵周吴徐孙马朱胡郭何高林罗")
STREETS = ["滨江路", "望江街", "青枫大道", "水厂巷", "环城北路", "春晖里"]


def _polygon(x0: int, y0: int) -> str:
    w, h = 20, 40
    return f"{x0},{y0};{x0+w},{y0};{x0+w},{y0+h};{x0},{y0+h}"


def seed(db: Session) -> None:
    if db.scalar(select(func.count(Zone.id))) > 0:
        return

    zones: list[Zone] = []
    for name, district, x0, y0 in ZONE_DEFS:
        zone = Zone(
            name=name,
            district=district,
            polygon=_polygon(x0, y0),
            centroid_x=x0 + 10,
            centroid_y=y0 + 20,
            users_count=10,
        )
        db.add(zone)
        zones.append(zone)
    db.flush()

    # ---- valves: corners + edge mids + one feed valve per zone ----
    valve_defs = []
    for i, (_, _, x0, y0) in enumerate(ZONE_DEFS):
        valve_defs += [
            (f"V{10+i*4}", f"{zones[i].name}西北阀", x0, y0, [i]),
            (f"V{11+i*4}", f"{zones[i].name}东北阀", x0 + 20, y0, [i]),
            (f"V{12+i*4}", f"{zones[i].name}西南阀", x0, y0 + 40, [i]),
            (f"V{13+i*4}", f"{zones[i].name}东南阀", x0 + 20, y0 + 40, [i]),
            (f"V{30+i}", f"{zones[i].name}进水主阀", x0 + 10, y0 - 4, [i]),
        ]
    valves: list[Valve] = []
    for code, name, x, y, zone_indexes in valve_defs:
        valve = Valve(code=code, name=name, location_x=x, location_y=y, diameter_mm=400)
        valve.zones = [zones[i] for i in zone_indexes]
        db.add(valve)
        valves.append(valve)

    # ---- pipes: mains connecting the three zone feed valves ----
    db.add(Pipe(code="P-01", from_x=15, from_y=6, to_x=50, to_y=6, diameter_mm=500))
    db.add(Pipe(code="P-02", from_x=50, from_y=6, to_x=85, to_y=6, diameter_mm=500))
    db.add(Pipe(code="P-03", from_x=15, from_y=30, to_x=50, to_y=30, diameter_mm=300))
    db.add(Pipe(code="P-04", from_x=50, from_y=30, to_x=85, to_y=30, diameter_mm=300))

    # ---- users: 10 per zone, first is a priority account (hospital/school) ----
    priority_names = ["滨江人民医院", "望湖中心小学", "青枫养老中心"]
    uid = 0
    for zi, (zone_name, _, x0, y0) in enumerate(ZONE_DEFS):
        for j in range(10):
            uid += 1
            col, row = j % 5, j // 5
            ux = x0 + 3 + col * 3.5
            uy = y0 + 8 + row * 22
            if j == 0:
                name, address, phone, priority = (
                    priority_names[zi], f"{zone_name}重点保障单位", "0571-88000000", True,
                )
            else:
                surname = USER_SURNAMES[(uid * 3 + zi) % len(USER_SURNAMES)]
                name = f"{surname}先生/女士"
                address = f"{STREETS[(uid+zi) % len(STREETS)]}{(j*7+zi*3) % 99 + 1}号"
                phone = f"139{uid:08d}"
                priority = False
            db.add(
                WaterUser(
                    name=name, phone=phone, address=address, zone_id=zones[zi].id,
                    priority=priority, location_x=ux, location_y=uy,
                )
            )

    # ---- teams ----
    team_defs = [
        ("抢修一班（城东驻地）", "陈建国", "13800000001", 50, 3),
        ("抢修二班（城西驻地）", "李志远", "13800000002", 2, 55),
        ("抢修三班（城南驻地）", "王海峰", "13800000003", 98, 55, "welding,pump"),
    ]
    for name, leader, phone, hx, hy, *skills in team_defs:
        db.add(
            Team(
                name=name, leader=leader, phone=phone,
                home_x=hx, home_y=hy, location_x=hx, location_y=hy,
                status=TeamStatus.available, skills=skills[0] if skills else "",
            )
        )

    # ---- materials ----
    for code, name, unit, stock, safety in MATERIAL_CATALOG:
        db.add(Material(code=code, name=name, unit=unit, stock=stock, safety_stock=safety))

    db.commit()
