\
from __future__ import annotations

import json


SYSTEM_PROMPT = """You are the high-level motion planner for a rectangular mobile rover.

Your only task is to convert the supplied natural-language instruction and world state into a short executable motion plan.

Coordinate and command conventions:
- World origin is the arena bottom-left.
- +X points right.
- +Y points up.
- Heading 0 degrees points +Y/up.
- Heading 90 degrees points +X/right.
- TURN uses signed degrees: positive = turn right/clockwise, negative = turn left/anticlockwise.
- FWD and BACK values are distances in millimetres.
- The rover has a rectangular physical footprint. Plan for the full rover body, not only its centre.
- Avoid every obstacle and keep the complete rover footprint inside the arena at all times.

Command limits:
- Maximum 12 commands total.
- TURN: 0 < absolute value <= 180 degrees.
- FWD: 0 < value <= 2000 mm.
- BACK: 0 < value <= 1000 mm.
- STOP must be the final command and may appear only once.

Do not use tools, web search, or outside knowledge.
Use only the supplied instruction and world state.
Return only the requested command-plan structure. Do not include explanations.
"""


def build_user_prompt(user_instruction: str, world_state: dict) -> str:
    return (
        "USER INSTRUCTION:\n"
        + user_instruction.strip()
        + "\n\nWORLD STATE:\n"
        + json.dumps(world_state, indent=2, sort_keys=True)
    )


def build_prompt_payload(user_instruction: str, world_state: dict) -> dict:
    return {
        "system": SYSTEM_PROMPT,
        "user": build_user_prompt(user_instruction, world_state),
    }
