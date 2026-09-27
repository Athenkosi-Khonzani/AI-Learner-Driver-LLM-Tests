import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pytest

from llm_test.commands.command_schema import (
    parse_plan,
    compile_wire_commands,
    CommandValidationError,
)


def test_valid_plan_compiles_to_wire_protocol():
    plan = {
        "cmds": [
            {"op": "TURN", "value": -30},
            {"op": "FWD", "value": 200},
            {"op": "STOP", "value": None},
        ]
    }

    commands = parse_plan(plan)

    assert compile_wire_commands(commands) == [
        ["TURN", -30],
        ["FWD", 200],
        ["STOP"],
    ]


def test_stop_is_required():
    with pytest.raises(CommandValidationError):
        parse_plan({
            "cmds": [
                {"op": "FWD", "value": 100}
            ]
        })
