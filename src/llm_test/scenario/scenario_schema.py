from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any
import json
from pathlib import Path


COLOURS = ("red", "green", "yellow", "blue")


@dataclass
class RoverSpec:
    x_mm: float = 400.0
    y_mm: float = 400.0
    length_mm: float = 180.0
    breadth_mm: float = 140.0
    heading_deg: float = 0.0


@dataclass
class BlockSpec:
    id: str
    colour: str
    x_mm: float
    y_mm: float
    length_mm: float = 300.0
    breadth_mm: float = 200.0
    orientation_deg: float = 0.0

    def __post_init__(self) -> None:
        if self.colour not in COLOURS:
            raise ValueError(f"Unsupported block colour: {self.colour}")


@dataclass
class GoalSpec:
    goal_type: str = "pose"
    target_x_mm: float = 2000.0
    target_y_mm: float = 2000.0
    position_tolerance_mm: float = 75.0
    require_heading: bool = False
    target_heading_deg: float = 0.0
    heading_tolerance_deg: float = 15.0


@dataclass
class Scenario:
    name: str = "untitled"
    arena_width_mm: float = 2500.0
    arena_height_mm: float = 2500.0
    rover: RoverSpec = field(default_factory=RoverSpec)
    blocks: list[BlockSpec] = field(default_factory=list)
    user_instruction: str = "Drive to the target safely."
    hidden_goal: GoalSpec = field(default_factory=GoalSpec)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Scenario":
        return cls(
            name=data.get("name", "untitled"),
            arena_width_mm=float(data.get("arena_width_mm", 2500.0)),
            arena_height_mm=float(data.get("arena_height_mm", 2500.0)),
            rover=RoverSpec(**data.get("rover", {})),
            blocks=[BlockSpec(**b) for b in data.get("blocks", [])],
            user_instruction=data.get("user_instruction", ""),
            hidden_goal=GoalSpec(**data.get("hidden_goal", {})),
        )

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Scenario":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)
