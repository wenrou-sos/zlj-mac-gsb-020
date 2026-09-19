"""Material bill-of-materials templates keyed by event severity / pipe diameter."""

# severity -> list of (material_code, qty per 100mm of pipe diameter factor)
# Quantities below are for a typical ~300mm main and scaled by diameter ratio.
MATERIAL_REQUIREMENTS: dict[str, list[tuple[str, float]]] = {
    "minor": [
        ("PIPE_CLAMP", 2),
        ("RUBBER_SEAL", 4),
        ("BOLT_SET", 8),
    ],
    "moderate": [
        ("PIPE_SECTION", 1),
        ("PIPE_CLAMP", 4),
        ("RUBBER_SEAL", 8),
        ("BOLT_SET", 16),
        ("WELDING_ROD", 10),
    ],
    "major": [
        ("PIPE_SECTION", 2),
        ("PIPE_CLAMP", 8),
        ("RUBBER_SEAL", 16),
        ("BOLT_SET", 32),
        ("WELDING_ROD", 25),
    ],
    "critical": [
        ("PIPE_SECTION", 4),
        ("PIPE_CLAMP", 12),
        ("RUBBER_SEAL", 32),
        ("BOLT_SET", 64),
        ("WELDING_ROD", 50),
    ],
}

# Base repair minutes per severity (before scaling / blockers)
REPAIR_MINUTES = {
    "minor": 45,
    "moderate": 90,
    "major": 150,
    "critical": 240,
}

VALVE_MINUTES = 15  # per valve operation
TRAVEL_SPEED_UNITS_PER_MIN = 0.9  # map units per minute
ROAD_CLOSURE_DETOUR_MIN = 30
MATERIAL_SHORTAGE_DELAY_MIN = 90
TEAM_SKILL_BONUS_UNITS = 6.0  # "welding" teams start this much closer for major+ events


def required_materials(severity: str, pipe_diameter_mm: int) -> dict[str, float]:
    scale = max(1.0, pipe_diameter_mm / 300.0)
    result: dict[str, float] = {}
    for code, qty in MATERIAL_REQUIREMENTS.get(severity, MATERIAL_REQUIREMENTS["minor"]):
        result[code] = round(qty * scale, 1) if code != "PIPE_SECTION" else max(1, round(qty * scale))
    return result
