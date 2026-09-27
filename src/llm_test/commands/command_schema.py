from __future__ import annotations

from dataclasses import dataclass
from typing import Any


VALID_OPS = {"TURN", "FWD", "BACK", "STOP"}

MAX_COMMANDS = 12
MAX_FWD_MM = 2000.0
MAX_BACK_MM = 1000.0
MAX_TURN_DEG = 180.0


@dataclass(frozen=True)
class Command:
    op: str
    value: float | None = None


class CommandValidationError(ValueError):
    pass


def parse_plan(data: dict[str, Any]) -> list[Command]:
    if not isinstance(data, dict):
        raise CommandValidationError("Plan must be a JSON object.")

    cmds = data.get("cmds")
    if not isinstance(cmds, list):
        raise CommandValidationError("'cmds' must be a list.")

    if not cmds:
        raise CommandValidationError("Command list cannot be empty.")

    if len(cmds) > MAX_COMMANDS:
        raise CommandValidationError(
            f"Too many commands: {len(cmds)} > {MAX_COMMANDS}."
        )

    parsed: list[Command] = []

    for index, item in enumerate(cmds):
        if not isinstance(item, dict):
            raise CommandValidationError(
                f"Command {index} must be an object."
            )

        op = str(item.get("op", "")).upper()
        if op not in VALID_OPS:
            raise CommandValidationError(
                f"Command {index} has invalid op '{op}'."
            )

        value = item.get("value")

        if op == "STOP":
            if value not in (None,):
                raise CommandValidationError(
                    "STOP must have value null or omit the value."
                )
            parsed.append(Command(op="STOP", value=None))
            continue

        if not isinstance(value, (int, float)):
            raise CommandValidationError(
                f"{op} requires a numeric value."
            )

        value = float(value)

        if op == "TURN":
            if value == 0 or abs(value) > MAX_TURN_DEG:
                raise CommandValidationError(
                    f"TURN must satisfy 0 < |value| <= {MAX_TURN_DEG}."
                )

        elif op == "FWD":
            if not (0 < value <= MAX_FWD_MM):
                raise CommandValidationError(
                    f"FWD must satisfy 0 < value <= {MAX_FWD_MM}."
                )

        elif op == "BACK":
            if not (0 < value <= MAX_BACK_MM):
                raise CommandValidationError(
                    f"BACK must satisfy 0 < value <= {MAX_BACK_MM}."
                )

        parsed.append(Command(op=op, value=value))

    if parsed[-1].op != "STOP":
        raise CommandValidationError(
            "The final command must be STOP."
        )

    if any(cmd.op == "STOP" for cmd in parsed[:-1]):
        raise CommandValidationError(
            "STOP may appear only as the final command."
        )

    return parsed


def compile_wire_commands(commands: list[Command]) -> list[list]:
    output: list[list] = []

    for cmd in commands:
        if cmd.op == "STOP":
            output.append(["STOP"])
        else:
            value = (
                int(cmd.value)
                if float(cmd.value).is_integer()
                else float(cmd.value)
            )
            output.append([cmd.op, value])

    return output
