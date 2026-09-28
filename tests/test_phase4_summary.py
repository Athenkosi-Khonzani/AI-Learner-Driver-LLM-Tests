import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_test.benchmark.pilot_summary import (
    generate_pilot_summary,
)


def _record(job_id, rep, wire, success=True, latency=1000.0):
    return {
        "benchmark_version": "x",
        "timestamp_utc": "x",
        "scenario_name": "BASIC_01",
        "scenario_path": "x",
        "provider_key": "openai_fast",
        "provider": "openai",
        "model": "test-model",
        "mode": "structured",
        "run_index": rep,
        "prompt_sha256": "x",
        "api_success": True,
        "api_latency_ms": latency,
        "validation_latency_ms": 1.0,
        "plan_ready_latency_ms": latency,
        "json_parse_success": True,
        "schema_valid": True,
        "protocol_valid": True,
        "simulation_executed": True,
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "cached_input_tokens": 0,
        "reasoning_tokens": 0,
        "estimated_cost_usd": 0.001,
        "response_id": "x",
        "finish_reason": "x",
        "error_type": None,
        "error_message": None,
        "raw_response": "",
        "parsed_plan": None,
        "wire_commands": wire,
        "task_success": success,
        "safe": True,
        "collision": False,
        "boundary_violation": False,
        "stop_reached": True,
        "final_x_mm": 1.0,
        "final_y_mm": 1.0,
        "final_heading_deg": 0.0,
        "position_error_mm": 1.0,
        "heading_error_deg": None,
        "travel_distance_mm": 100.0,
        "total_rotation_deg": 0.0,
        "commands_executed": 2,
        "job_id": job_id,
        "scenario_family": "basic_motion",
        "scenario_difficulty": 1,
        "scenario_title": "test",
        "repetition_index": rep,
        "execution_order": rep,
        "cache_buster_nonce": str(rep),
        "transmitted_prompt_sha256": str(rep),
    }


def test_summary_detects_plan_nondeterminism(tmp_path):
    session_dir = tmp_path / "session"
    records_dir = session_dir / "records"
    records_dir.mkdir(parents=True)

    rows = [
        _record(
            "BASIC_01__r1__openai_fast",
            1,
            [["FWD", 100], ["STOP"]],
        ),
        _record(
            "BASIC_01__r2__openai_fast",
            2,
            [["FWD", 100], ["STOP"]],
        ),
        _record(
            "BASIC_01__r3__openai_fast",
            3,
            [["TURN", 1], ["FWD", 100], ["STOP"]],
        ),
    ]

    for row in rows:
        (
            records_dir / f"{row['job_id']}.json"
        ).write_text(
            json.dumps(
                {"request": {}, "record": row}
            ),
            encoding="utf-8",
        )

    plan = {
        "pilot_version": "test",
        "session_id": "test",
        "seed": 1,
        "cache_busting_enabled": True,
        "repetitions_per_scenario": 3,
        "jobs": [
            {"provider_key": "openai_fast"}
            for _ in range(3)
        ],
    }

    summary = generate_pilot_summary(
        session_dir,
        plan,
    )

    consistency = summary[
        "scenario_consistency"
    ][0]

    assert consistency["unique_valid_plans"] == 2
    assert consistency["all_repetitions_identical"] is False
    assert consistency["outcome_consistent"] is True

    model = summary["provider_summary"][0]
    assert model["scenarios_all_3_plans_identical_rate"] == 0.0
    assert model["scenarios_outcome_consistent_rate"] == 1.0
