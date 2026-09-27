import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_test.scenario.scenario_schema import Scenario, BlockSpec
from llm_test.scenario.world_state_builder import build_world_state


def test_world_state_contains_rover_footprint():
    scenario = Scenario()
    state = build_world_state(scenario)

    assert state["rover"]["footprint_mm"]["length"] == scenario.rover.length_mm
    assert state["rover"]["footprint_mm"]["breadth"] == scenario.rover.breadth_mm


def test_world_state_generates_block_polygon():
    scenario = Scenario(
        blocks=[
            BlockSpec(
                id="blue_block_01",
                colour="blue",
                x_mm=1000,
                y_mm=1000,
                length_mm=300,
                breadth_mm=200,
                orientation_deg=45,
            )
        ]
    )

    state = build_world_state(scenario)

    assert len(state["obstacles"][0]["polygon_mm"]) == 4
