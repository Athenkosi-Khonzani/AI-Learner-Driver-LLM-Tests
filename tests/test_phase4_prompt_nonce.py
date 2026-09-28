import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_test.benchmark.prompt_builder import build_prompt_payload
from llm_test.scenario.scenario_schema import Scenario
from llm_test.scenario.world_state_builder import build_world_state


def test_nonce_changes_literal_prompt_but_not_user_task():
    scenario = Scenario()
    world = build_world_state(scenario)

    a = build_prompt_payload(
        scenario.user_instruction,
        world,
        benchmark_nonce="aaaaaaaa",
    )
    b = build_prompt_payload(
        scenario.user_instruction,
        world,
        benchmark_nonce="bbbbbbbb",
    )
    canonical = build_prompt_payload(
        scenario.user_instruction,
        world,
        benchmark_nonce=None,
    )

    assert a["system"] != b["system"]
    assert a["user"] == b["user"] == canonical["user"]

    # The frozen planner instructions after the nonce prefix remain identical.
    assert canonical["system"] in a["system"]
    assert canonical["system"] in b["system"]
