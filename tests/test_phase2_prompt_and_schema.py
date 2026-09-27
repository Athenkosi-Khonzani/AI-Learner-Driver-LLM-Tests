\
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_test.benchmark.output_models import StructuredPlan
from llm_test.benchmark.prompt_builder import build_prompt_payload
from llm_test.scenario.scenario_schema import Scenario
from llm_test.scenario.world_state_builder import build_world_state


def test_structured_plan_schema_accepts_required_shape():
    plan = StructuredPlan.model_validate({
        "cmds": [
            {"op": "FWD", "value": 500},
            {"op": "STOP", "value": None},
        ]
    })

    assert plan.cmds[-1].op == "STOP"


def test_hidden_goal_is_not_in_prompt_payload():
    scenario = Scenario()
    state = build_world_state(scenario)

    payload = build_prompt_payload(
        scenario.user_instruction,
        state,
    )

    combined = payload["system"] + payload["user"]

    assert "hidden_goal" not in combined
    assert "target_x_mm" not in combined
