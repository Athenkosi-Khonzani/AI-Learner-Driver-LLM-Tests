import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from llm_test.analysis.core import failure_mode, model_metrics, wilson_interval

def _row(provider, success=True, collision=False, boundary=False, plan=None, rep=1):
    return {
        "provider_key": provider,
        "model": "test",
        "scenario_name": "S1",
        "scenario_family": "basic_motion",
        "scenario_difficulty": 1,
        "repetition_index": rep,
        "api_success": True,
        "schema_valid": True,
        "protocol_valid": True,
        "simulation_executed": True,
        "task_success": success,
        "collision": collision,
        "boundary_violation": boundary,
        "plan_ready_latency_ms": 1000 + rep,
        "position_error_mm": 10,
        "commands_executed": 2,
        "travel_distance_mm": 500,
        "total_rotation_deg": 0,
        "estimated_cost_usd": 0.001,
        "wire_commands": plan or [["FWD", 500], ["STOP"]],
        "cached_input_tokens": 0,
    }

def test_wilson_interval_contains_observed_rate():
    low, high = wilson_interval(8, 10)
    assert low < 0.8 < high

def test_failure_mode_is_mutually_classified():
    assert failure_mode(_row("x", success=True)) == "Success"
    assert failure_mode(_row("x", success=False, collision=True)) == "Collision"

def test_repeatability_metrics_detect_identical_three_runs():
    rows = [_row("openai_fast", rep=1), _row("openai_fast", rep=2), _row("openai_fast", rep=3)]
    metrics = model_metrics(rows)
    assert len(metrics) == 1
    assert metrics[0]["all_3_plans_identical_rate"] == 1.0
    assert metrics[0]["outcome_consistent_rate"] == 1.0
