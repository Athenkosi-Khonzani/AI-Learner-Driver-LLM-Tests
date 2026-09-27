
from __future__ import annotations

from dataclasses import dataclass
import heapq
import math

from llm_test.scenario.scenario_schema import Scenario


@dataclass
class FeasibilityResult:
    feasible: bool
    reason: str
    path: list[tuple[float, float]]
    path_length_mm: float | None
    clearance_radius_mm: float


def _rotate_to_local(
    x: float,
    y: float,
    cx: float,
    cy: float,
    heading_deg: float,
) -> tuple[float, float]:
    """
    Convert a world point into the local frame of a rectangle whose length
    axis points along the project heading convention:
      0 deg = +Y
      90 deg = +X
    """
    theta = math.radians(heading_deg)
    dx = x - cx
    dy = y - cy

    # local right and forward axes
    right_x = math.cos(theta)
    right_y = -math.sin(theta)
    fwd_x = math.sin(theta)
    fwd_y = math.cos(theta)

    local_r = dx * right_x + dy * right_y
    local_f = dx * fwd_x + dy * fwd_y
    return local_r, local_f


def _point_inside_inflated_block(
    x: float,
    y: float,
    block,
    inflate_mm: float,
) -> bool:
    local_r, local_f = _rotate_to_local(
        x, y,
        block.x_mm, block.y_mm,
        block.orientation_deg,
    )

    half_b = block.breadth_mm / 2.0 + inflate_mm
    half_l = block.length_mm / 2.0 + inflate_mm

    return abs(local_r) <= half_b and abs(local_f) <= half_l


def _point_safe(
    x: float,
    y: float,
    scenario: Scenario,
    clearance_radius_mm: float,
) -> bool:
    # Conservative arena clearance. If the rover's circumscribed circle is
    # inside the arena, then its rectangular footprint is inside at any heading.
    if not (
        clearance_radius_mm <= x <= scenario.arena_width_mm - clearance_radius_mm
        and clearance_radius_mm <= y <= scenario.arena_height_mm - clearance_radius_mm
    ):
        return False

    for block in scenario.blocks:
        if _point_inside_inflated_block(
            x, y, block, clearance_radius_mm
        ):
            return False

    return True


def _path_length(path: list[tuple[float, float]]) -> float:
    if len(path) < 2:
        return 0.0
    return sum(
        math.hypot(x2 - x1, y2 - y1)
        for (x1, y1), (x2, y2) in zip(path, path[1:])
    )


def conservative_feasibility(
    scenario: Scenario,
    grid_mm: float = 50.0,
) -> FeasibilityResult:
    """
    Conservative proof-of-feasibility for the benchmark dataset.

    The rectangular rover is enclosed by its circumscribed circle:
        radius = 0.5 * hypot(length, breadth)

    Obstacles and arena boundaries are inflated/shrunk by that radius. A path
    found for the circle is therefore safe for the real rectangle at any heading,
    including during in-place rotations.

    This validator is deliberately NOT the benchmark planner and its path is
    never shown to an LLM.
    """
    rover = scenario.rover
    radius = 0.5 * math.hypot(rover.length_mm, rover.breadth_mm)

    sx, sy = rover.x_mm, rover.y_mm
    gx = scenario.hidden_goal.target_x_mm
    gy = scenario.hidden_goal.target_y_mm

    if not _point_safe(sx, sy, scenario, radius):
        return FeasibilityResult(
            feasible=False,
            reason="start_pose_not_conservatively_safe",
            path=[],
            path_length_mm=None,
            clearance_radius_mm=radius,
        )

    if not _point_safe(gx, gy, scenario, radius):
        return FeasibilityResult(
            feasible=False,
            reason="goal_pose_not_conservatively_safe",
            path=[],
            path_length_mm=None,
            clearance_radius_mm=radius,
        )

    def snap(v: float) -> int:
        return int(round(v / grid_mm))

    start = (snap(sx), snap(sy))
    goal = (snap(gx), snap(gy))

    def world(node):
        return node[0] * grid_mm, node[1] * grid_mm

    if not _point_safe(*world(start), scenario, radius):
        # Search a very small neighborhood for a safe grid representative.
        candidates = []
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                n = (start[0] + dx, start[1] + dy)
                wx, wy = world(n)
                if _point_safe(wx, wy, scenario, radius):
                    candidates.append(
                        (math.hypot(wx - sx, wy - sy), n)
                    )
        if not candidates:
            return FeasibilityResult(
                feasible=False,
                reason="no_safe_start_grid_node",
                path=[],
                path_length_mm=None,
                clearance_radius_mm=radius,
            )
        start = min(candidates)[1]

    if not _point_safe(*world(goal), scenario, radius):
        candidates = []
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                n = (goal[0] + dx, goal[1] + dy)
                wx, wy = world(n)
                if _point_safe(wx, wy, scenario, radius):
                    candidates.append(
                        (math.hypot(wx - gx, wy - gy), n)
                    )
        if not candidates:
            return FeasibilityResult(
                feasible=False,
                reason="no_safe_goal_grid_node",
                path=[],
                path_length_mm=None,
                clearance_radius_mm=radius,
            )
        goal = min(candidates)[1]

    moves = [
        (1, 0, 1.0), (-1, 0, 1.0),
        (0, 1, 1.0), (0, -1, 1.0),
        (1, 1, math.sqrt(2)), (1, -1, math.sqrt(2)),
        (-1, 1, math.sqrt(2)), (-1, -1, math.sqrt(2)),
    ]

    def heuristic(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    open_heap = [(heuristic(start, goal), 0.0, start)]
    came_from = {}
    g_score = {start: 0.0}
    visited = set()

    while open_heap:
        _, g, current = heapq.heappop(open_heap)
        if current in visited:
            continue
        visited.add(current)

        if current == goal:
            nodes = [current]
            while current in came_from:
                current = came_from[current]
                nodes.append(current)
            nodes.reverse()

            path = [(sx, sy)]
            path.extend(world(n) for n in nodes[1:-1])
            path.append((gx, gy))

            return FeasibilityResult(
                feasible=True,
                reason="conservative_path_found",
                path=path,
                path_length_mm=_path_length(path),
                clearance_radius_mm=radius,
            )

        for dx, dy, move_cost in moves:
            neighbor = (current[0] + dx, current[1] + dy)
            wx, wy = world(neighbor)

            if not _point_safe(wx, wy, scenario, radius):
                continue

            tentative = g + move_cost
            if tentative < g_score.get(neighbor, float("inf")):
                g_score[neighbor] = tentative
                came_from[neighbor] = current
                heapq.heappush(
                    open_heap,
                    (
                        tentative + heuristic(neighbor, goal),
                        tentative,
                        neighbor,
                    )
                )

    return FeasibilityResult(
        feasible=False,
        reason="no_conservative_path_found",
        path=[],
        path_length_mm=None,
        clearance_radius_mm=radius,
    )
