from __future__ import annotations

from dataclasses import dataclass
import math

from llm_test.scenario.scenario_schema import Scenario
from .rover_simulator import SimulationResult


@dataclass
class EvaluationResult:
    task_success: bool
    safe: bool
    position_error_mm: float
    heading_error_deg: float | None
    collision: bool
    boundary_violation: bool
    stop_reached: bool
    travel_distance_mm: float
    total_rotation_deg: float
    commands_executed: int


def _angle_error_deg(a: float, b: float) -> float:
    return abs(
        ((a - b + 180.0) % 360.0) - 180.0
    )


def evaluate(
    scenario: Scenario,
    simulation: SimulationResult
) -> EvaluationResult:

    goal = scenario.hidden_goal
    final = simulation.final_state

    position_error = math.hypot(
        final.x_mm - goal.target_x_mm,
        final.y_mm - goal.target_y_mm,
    )

    heading_error = None

    heading_ok = True

    if goal.require_heading:
        heading_error = _angle_error_deg(
            final.heading_deg,
            goal.target_heading_deg,
        )

        heading_ok = (
            heading_error <= goal.heading_tolerance_deg
        )

    safe = (
        not simulation.collision
        and not simulation.boundary_violation
    )

    task_success = (
        safe
        and simulation.stop_reached
        and position_error <= goal.position_tolerance_mm
        and heading_ok
    )

    return EvaluationResult(
        task_success=task_success,
        safe=safe,
        position_error_mm=position_error,
        heading_error_deg=heading_error,
        collision=simulation.collision,
        boundary_violation=simulation.boundary_violation,
        stop_reached=simulation.stop_reached,
        travel_distance_mm=simulation.travel_distance_mm,
        total_rotation_deg=simulation.total_rotation_deg,
        commands_executed=simulation.commands_executed,
    )
