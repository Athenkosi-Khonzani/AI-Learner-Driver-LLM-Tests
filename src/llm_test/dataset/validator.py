
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import math

from llm_test.scenario.scenario_schema import Scenario
from .feasibility import conservative_feasibility


EXPECTED_FAMILY_COUNTS = {
    "basic_motion": 4,
    "coordinate_navigation": 4,
    "object_target": 5,
    "single_obstacle": 5,
    "multi_obstacle": 6,
    "tight_boundary": 6,
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_manifest(project_root: Path) -> dict:
    manifest_path = project_root / "dataset" / "benchmark_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    entries = manifest["scenarios"]
    report_entries = []
    family_counts: dict[str, int] = {}

    ids = [entry["id"] for entry in entries]
    duplicate_ids = sorted(
        {scenario_id for scenario_id in ids if ids.count(scenario_id) > 1}
    )

    for entry in entries:
        scenario_path = project_root / "dataset" / entry["file"]
        problems = []

        if not scenario_path.exists():
            problems.append("scenario_file_missing")
            report_entries.append({
                "id": entry["id"],
                "valid": False,
                "problems": problems,
            })
            continue

        actual_hash = sha256_file(scenario_path)
        if actual_hash != entry["sha256"]:
            problems.append("sha256_mismatch")

        try:
            scenario = Scenario.load(scenario_path)
        except Exception as exc:
            problems.append(f"load_error:{type(exc).__name__}:{exc}")
            report_entries.append({
                "id": entry["id"],
                "valid": False,
                "problems": problems,
            })
            continue

        if scenario.name != entry["id"]:
            problems.append("scenario_name_does_not_match_manifest_id")

        if not scenario.user_instruction.strip():
            problems.append("empty_user_instruction")

        if len(scenario.blocks) != entry["obstacle_count"]:
            problems.append("obstacle_count_mismatch")

        family_counts[entry["family"]] = (
            family_counts.get(entry["family"], 0) + 1
        )

        # Check all block IDs are unique.
        block_ids = [b.id for b in scenario.blocks]
        if len(block_ids) != len(set(block_ids)):
            problems.append("duplicate_block_ids")

        # Basic coordinate sanity.
        r = scenario.rover
        if not (0 <= r.x_mm <= scenario.arena_width_mm):
            problems.append("rover_x_outside_arena")
        if not (0 <= r.y_mm <= scenario.arena_height_mm):
            problems.append("rover_y_outside_arena")

        g = scenario.hidden_goal
        if not (0 <= g.target_x_mm <= scenario.arena_width_mm):
            problems.append("goal_x_outside_arena")
        if not (0 <= g.target_y_mm <= scenario.arena_height_mm):
            problems.append("goal_y_outside_arena")

        feasibility = conservative_feasibility(scenario)
        if not feasibility.feasible:
            problems.append(
                f"not_conservatively_feasible:{feasibility.reason}"
            )

        report_entries.append({
            "id": entry["id"],
            "family": entry["family"],
            "difficulty": entry["difficulty"],
            "valid": not problems,
            "problems": problems,
            "conservative_feasible": feasibility.feasible,
            "reference_path_length_mm": (
                round(feasibility.path_length_mm, 1)
                if feasibility.path_length_mm is not None
                else None
            ),
            "clearance_radius_mm": round(
                feasibility.clearance_radius_mm, 2
            ),
        })

    count_ok = len(entries) == 30
    family_counts_ok = family_counts == EXPECTED_FAMILY_COUNTS

    all_valid = (
        count_ok
        and family_counts_ok
        and not duplicate_ids
        and all(item["valid"] for item in report_entries)
    )

    return {
        "dataset_name": manifest["dataset_name"],
        "dataset_version": manifest["dataset_version"],
        "locked": manifest.get("locked", False),
        "scenario_count": len(entries),
        "expected_scenario_count": 30,
        "scenario_count_ok": count_ok,
        "family_counts": family_counts,
        "expected_family_counts": EXPECTED_FAMILY_COUNTS,
        "family_counts_ok": family_counts_ok,
        "duplicate_ids": duplicate_ids,
        "all_valid": all_valid,
        "scenarios": report_entries,
    }
