
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_test.dataset.validator import validate_manifest
from llm_test.scenario.scenario_schema import Scenario
from llm_test.scenario.world_state_builder import build_world_state


def test_dataset_has_30_valid_scenarios():
    report = validate_manifest(ROOT)
    assert report["scenario_count"] == 30
    assert report["all_valid"] is True


def test_hidden_goal_not_present_in_generated_world_state():
    manifest = json.loads(
        (ROOT / "dataset" / "benchmark_manifest.json")
        .read_text(encoding="utf-8")
    )

    for entry in manifest["scenarios"]:
        scenario = Scenario.load(
            ROOT / "dataset" / entry["file"]
        )
        state = build_world_state(scenario)
        serialized = json.dumps(state)
        assert "hidden_goal" not in serialized
        assert "target_x_mm" not in serialized


def test_dataset_manifest_is_locked():
    manifest = json.loads(
        (ROOT / "dataset" / "benchmark_manifest.json")
        .read_text(encoding="utf-8")
    )
    assert manifest["locked"] is True
