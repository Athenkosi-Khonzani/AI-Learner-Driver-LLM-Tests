from __future__ import annotations

import math
from dataclasses import dataclass


Point = tuple[float, float]


@dataclass
class RectPose:
    x_mm: float
    y_mm: float
    length_mm: float
    breadth_mm: float
    heading_deg: float


def rectangle_polygon(rect: RectPose) -> list[Point]:
    theta = math.radians(rect.heading_deg)

    forward = (
        math.sin(theta),
        math.cos(theta)
    )

    right = (
        math.cos(theta),
        -math.sin(theta)
    )

    hl = rect.length_mm / 2.0
    hb = rect.breadth_mm / 2.0

    return [
        (
            rect.x_mm + f * forward[0] + r * right[0],
            rect.y_mm + f * forward[1] + r * right[1],
        )
        for f, r in (
            (hl, hb),
            (hl, -hb),
            (-hl, -hb),
            (-hl, hb),
        )
    ]


def _edge_normals(poly: list[Point]) -> list[Point]:
    normals: list[Point] = []

    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]

        ex = x2 - x1
        ey = y2 - y1

        nx = -ey
        ny = ex

        length = math.hypot(nx, ny)
        if length > 0:
            normals.append((nx / length, ny / length))

    return normals


def _project(poly: list[Point], axis: Point) -> tuple[float, float]:
    values = [
        x * axis[0] + y * axis[1]
        for x, y in poly
    ]
    return min(values), max(values)


def polygons_intersect(
    poly_a: list[Point],
    poly_b: list[Point]
) -> bool:
    """
    Separating Axis Theorem for convex polygons.
    Touching is treated as collision.
    """
    for axis in _edge_normals(poly_a) + _edge_normals(poly_b):
        a_min, a_max = _project(poly_a, axis)
        b_min, b_max = _project(poly_b, axis)

        if a_max < b_min or b_max < a_min:
            return False

    return True


def polygon_inside_arena(
    poly: list[Point],
    width_mm: float,
    height_mm: float
) -> bool:
    return all(
        0.0 <= x <= width_mm
        and 0.0 <= y <= height_mm
        for x, y in poly
    )
