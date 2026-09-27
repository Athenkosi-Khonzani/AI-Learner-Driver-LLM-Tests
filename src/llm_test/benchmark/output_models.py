\
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict


class PlannedCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["TURN", "FWD", "BACK", "STOP"]
    value: float | None


class StructuredPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cmds: list[PlannedCommand]
