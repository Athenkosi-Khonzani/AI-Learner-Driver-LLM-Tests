from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import math

from llm_test.commands.command_schema import parse_plan
from llm_test.scenario.scenario_schema import Scenario
from llm_test.simulator.rover_simulator import RoverSimulator, SimulationResult
from llm_test.simulator.evaluator import EvaluationResult, evaluate


@dataclass
class ReplayBundle:
    record_path: Path
    record: dict[str, Any]
    request: dict[str, Any]
    scenario: Scenario
    simulation: SimulationResult
    evaluation: EvaluationResult
    verification_ok: bool
    verification_messages: list[str]


def manifest_scenario_map(project_root: Path) -> dict[str, Path]:
    manifest_path = project_root / "dataset" / "benchmark_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        entry["id"]: project_root / "dataset" / entry["file"]
        for entry in manifest["scenarios"]
    }


def load_replay_bundle(project_root: Path, record_path: Path) -> ReplayBundle:
    payload = json.loads(record_path.read_text(encoding="utf-8"))
    record = payload["record"]
    request = payload.get("request", {})

    scenario_map = manifest_scenario_map(project_root)
    scenario_name = record["scenario_name"]
    if scenario_name not in scenario_map:
        raise KeyError(f"Scenario {scenario_name!r} is not present in the frozen dataset manifest.")

    scenario = Scenario.load(scenario_map[scenario_name])
    parsed_plan = record.get("parsed_plan")
    if parsed_plan is None:
        raise ValueError("This benchmark record has no parsed executable plan to replay.")

    commands = parse_plan(parsed_plan)
    simulation = RoverSimulator(scenario).simulate(commands)
    evaluation = evaluate(scenario, simulation)

    messages: list[str] = []

    def check_bool(name: str, recomputed: bool):
        stored = record.get(name)
        if stored is not None and bool(stored) != bool(recomputed):
            messages.append(f"{name}: stored={stored}, recomputed={recomputed}")

    check_bool("task_success", evaluation.task_success)
    check_bool("collision", evaluation.collision)
    check_bool("boundary_violation", evaluation.boundary_violation)
    check_bool("stop_reached", evaluation.stop_reached)

    for name, recomputed in (
        ("final_x_mm", simulation.final_state.x_mm),
        ("final_y_mm", simulation.final_state.y_mm),
        ("final_heading_deg", simulation.final_state.heading_deg),
    ):
        stored = record.get(name)
        if stored is not None and not math.isclose(float(stored), float(recomputed), abs_tol=1e-6):
            messages.append(f"{name}: stored={stored}, recomputed={recomputed}")

    return ReplayBundle(
        record_path=record_path,
        record=record,
        request=request,
        scenario=scenario,
        simulation=simulation,
        evaluation=evaluation,
        verification_ok=not messages,
        verification_messages=messages,
    )
