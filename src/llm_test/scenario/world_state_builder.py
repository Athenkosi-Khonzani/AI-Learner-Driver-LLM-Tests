from __future__ import annotations

import math
from .scenario_schema import Scenario, BlockSpec


def _rotated_rectangle_polygon(
    cx: float,
    cy: float,
    length: float,
    breadth: float,
    heading_deg: float,
) -> list[dict]:
    """
    Rectangle length axis points along heading convention:
    0 deg = +Y, 90 deg = +X.
    """
    theta = math.radians(heading_deg)
    forward = (math.sin(theta), math.cos(theta))
    right = (math.cos(theta), -math.sin(theta))

    hl = length / 2.0
    hb = breadth / 2.0

    pts = []
    for f, r in ((hl, hb), (hl, -hb), (-hl, -hb), (-hl, hb)):
        x = cx + f * forward[0] + r * right[0]
        y = cy + f * forward[1] + r * right[1]
        pts.append({"x": round(x, 1), "y": round(y, 1)})
    return pts


def build_world_state(scenario: Scenario) -> dict:
    rover = scenario.rover

    obstacles = []
    for block in scenario.blocks:
        obstacles.append({
            "id": block.id,
            "type": "coloured_block",
            "colour": block.colour,
            "centre_mm": {
                "x": round(block.x_mm, 1),
                "y": round(block.y_mm, 1),
            },
            "size_mm": {
                "length": round(block.length_mm, 1),
                "breadth": round(block.breadth_mm, 1),
            },
            "orientation_deg": round(block.orientation_deg, 1),
            "polygon_mm": _rotated_rectangle_polygon(
                block.x_mm,
                block.y_mm,
                block.length_mm,
                block.breadth_mm,
                block.orientation_deg,
            ),
        })

    return {
        "schema": "ai_learner_world_state",
        "schema_version": "benchmark-1.0",
        "coordinate_frame": {
            "units": "mm",
            "origin": "arena_bottom_left",
            "x_axis": "right",
            "y_axis": "up",
            "heading": {
                "0_deg": "+Y/up",
                "90_deg": "+X/right",
                "180_deg": "-Y/down",
                "270_deg": "-X/left",
            },
        },
        "arena": {
            "width_mm": round(scenario.arena_width_mm, 1),
            "height_mm": round(scenario.arena_height_mm, 1),
        },
        "rover": {
            "pose": {
                "x_mm": round(rover.x_mm, 1),
                "y_mm": round(rover.y_mm, 1),
                "heading_deg": round(rover.heading_deg % 360.0, 1),
            },
            "footprint_mm": {
                "length": round(rover.length_mm, 1),
                "breadth": round(rover.breadth_mm, 1),
            },
        },
        "obstacles": obstacles,
    }
