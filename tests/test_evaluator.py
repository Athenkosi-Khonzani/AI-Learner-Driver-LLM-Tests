import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_test.scenario.scenario_schema import Scenario
from llm_test.commands.command_schema import parse_plan
from llm_test.simulator.rover_simulator import RoverSimulator
from llm_test.simulator.evaluator import evaluate


def test_hidden_goal_success():
    scenario = Scenario()
    scenario.rover.x_mm = 500
    scenario.rover.y_mm = 500
    scenario.rover.heading_deg = 0

    scenario.hidden_goal.target_x_mm = 500
    scenario.hidden_goal.target_y_mm = 700
    scenario.hidden_goal.position_tolerance_mm = 5

    commands = parse_plan({
        "cmds": [
            {"op": "FWD", "value": 200},
            {"op": "STOP", "value": None},
        ]
    })

    simulation = RoverSimulator(scenario).simulate(commands)
    score = evaluate(scenario, simulation)

    assert score.task_success is True
    assert score.safe is True
