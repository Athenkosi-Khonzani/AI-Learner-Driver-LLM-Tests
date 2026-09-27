import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_test.scenario.scenario_schema import Scenario, BlockSpec
from llm_test.commands.command_schema import parse_plan
from llm_test.simulator.rover_simulator import RoverSimulator


def test_turn_positive_is_right():
    scenario = Scenario()
    scenario.rover.x_mm = 500
    scenario.rover.y_mm = 500
    scenario.rover.heading_deg = 0

    commands = parse_plan({
        "cmds": [
            {"op": "TURN", "value": 90},
            {"op": "STOP", "value": None},
        ]
    })

    result = RoverSimulator(scenario).simulate(commands)

    assert abs(result.final_state.heading_deg - 90) < 1e-9


def test_heading_90_forward_moves_positive_x():
    scenario = Scenario()
    scenario.rover.x_mm = 500
    scenario.rover.y_mm = 500
    scenario.rover.heading_deg = 90

    commands = parse_plan({
        "cmds": [
            {"op": "FWD", "value": 100},
            {"op": "STOP", "value": None},
        ]
    })

    result = RoverSimulator(scenario).simulate(commands)

    assert result.final_state.x_mm > 590
    assert abs(result.final_state.y_mm - 500) < 1e-6


def test_full_body_collision_is_detected():
    scenario = Scenario(
        blocks=[
            BlockSpec(
                id="red_block_01",
                colour="red",
                x_mm=500,
                y_mm=750,
                length_mm=200,
                breadth_mm=200,
            )
        ]
    )

    scenario.rover.x_mm = 500
    scenario.rover.y_mm = 400
    scenario.rover.heading_deg = 0
    scenario.rover.length_mm = 180
    scenario.rover.breadth_mm = 140

    commands = parse_plan({
        "cmds": [
            {"op": "FWD", "value": 500},
            {"op": "STOP", "value": None},
        ]
    })

    result = RoverSimulator(scenario).simulate(commands)

    assert result.collision is True
    assert result.stop_reached is False
