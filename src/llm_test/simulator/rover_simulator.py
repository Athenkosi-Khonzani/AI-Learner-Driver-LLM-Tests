from __future__ import annotations

from dataclasses import dataclass
import math

from llm_test.commands.command_schema import Command
from llm_test.scenario.scenario_schema import Scenario
from .geometry import (
    RectPose,
    rectangle_polygon,
    polygons_intersect,
    polygon_inside_arena,
)


TRANSLATION_STEP_MM = 5.0
ROTATION_STEP_DEG = 1.0


@dataclass
class SimulationState:
    x_mm: float
    y_mm: float
    heading_deg: float


@dataclass
class SimulationResult:
    states: list[SimulationState]
    final_state: SimulationState
    collision: bool
    boundary_violation: bool
    stop_reached: bool
    travel_distance_mm: float
    total_rotation_deg: float
    commands_executed: int
    failure_reason: str | None


class RoverSimulator:
    def __init__(self, scenario: Scenario):
        self.scenario = scenario

    def _rover_poly(self, state: SimulationState):
        rover = self.scenario.rover
        return rectangle_polygon(
            RectPose(
                x_mm=state.x_mm,
                y_mm=state.y_mm,
                length_mm=rover.length_mm,
                breadth_mm=rover.breadth_mm,
                heading_deg=state.heading_deg,
            )
        )

    def _block_polys(self):
        return [
            rectangle_polygon(
                RectPose(
                    x_mm=b.x_mm,
                    y_mm=b.y_mm,
                    length_mm=b.length_mm,
                    breadth_mm=b.breadth_mm,
                    heading_deg=b.orientation_deg,
                )
            )
            for b in self.scenario.blocks
        ]

    def _validate_pose(
        self,
        state: SimulationState
    ) -> tuple[bool, bool]:
        rover_poly = self._rover_poly(state)

        boundary = not polygon_inside_arena(
            rover_poly,
            self.scenario.arena_width_mm,
            self.scenario.arena_height_mm,
        )

        collision = any(
            polygons_intersect(rover_poly, block_poly)
            for block_poly in self._block_polys()
        )

        return collision, boundary

    def simulate(
        self,
        commands: list[Command]
    ) -> SimulationResult:

        state = SimulationState(
            x_mm=self.scenario.rover.x_mm,
            y_mm=self.scenario.rover.y_mm,
            heading_deg=self.scenario.rover.heading_deg % 360.0,
        )

        states = [SimulationState(**state.__dict__)]

        collision = False
        boundary = False
        stop_reached = False
        travel = 0.0
        rotation = 0.0
        executed = 0
        failure_reason = None

        for command in commands:
            executed += 1

            if command.op == "STOP":
                stop_reached = True
                break

            if command.op == "TURN":
                target = float(command.value)
                direction = 1.0 if target > 0 else -1.0
                remaining = abs(target)

                while remaining > 1e-9:
                    step = min(ROTATION_STEP_DEG, remaining)
                    state.heading_deg = (
                        state.heading_deg + direction * step
                    ) % 360.0

                    rotation += step
                    states.append(SimulationState(**state.__dict__))

                    collision, boundary = self._validate_pose(state)
                    if collision or boundary:
                        failure_reason = (
                            "collision"
                            if collision
                            else "boundary_violation"
                        )
                        return SimulationResult(
                            states=states,
                            final_state=state,
                            collision=collision,
                            boundary_violation=boundary,
                            stop_reached=stop_reached,
                            travel_distance_mm=travel,
                            total_rotation_deg=rotation,
                            commands_executed=executed,
                            failure_reason=failure_reason,
                        )

                    remaining -= step

            elif command.op in ("FWD", "BACK"):
                signed_distance = (
                    float(command.value)
                    if command.op == "FWD"
                    else -float(command.value)
                )

                direction = 1.0 if signed_distance > 0 else -1.0
                remaining = abs(signed_distance)

                while remaining > 1e-9:
                    step = min(TRANSLATION_STEP_MM, remaining)
                    signed_step = direction * step

                    theta = math.radians(state.heading_deg)

                    state.x_mm += (
                        math.sin(theta) * signed_step
                    )

                    state.y_mm += (
                        math.cos(theta) * signed_step
                    )

                    travel += step
                    states.append(SimulationState(**state.__dict__))

                    collision, boundary = self._validate_pose(state)
                    if collision or boundary:
                        failure_reason = (
                            "collision"
                            if collision
                            else "boundary_violation"
                        )
                        return SimulationResult(
                            states=states,
                            final_state=state,
                            collision=collision,
                            boundary_violation=boundary,
                            stop_reached=stop_reached,
                            travel_distance_mm=travel,
                            total_rotation_deg=rotation,
                            commands_executed=executed,
                            failure_reason=failure_reason,
                        )

                    remaining -= step

        return SimulationResult(
            states=states,
            final_state=state,
            collision=collision,
            boundary_violation=boundary,
            stop_reached=stop_reached,
            travel_distance_mm=travel,
            total_rotation_deg=rotation,
            commands_executed=executed,
            failure_reason=failure_reason,
        )
