\
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class BenchmarkRecord:
    benchmark_version: str
    timestamp_utc: str
    scenario_name: str
    scenario_path: str
    provider_key: str
    provider: str
    model: str
    mode: str
    run_index: int

    prompt_sha256: str
    api_success: bool
    api_latency_ms: float
    validation_latency_ms: float
    plan_ready_latency_ms: float

    json_parse_success: bool
    schema_valid: bool
    protocol_valid: bool
    simulation_executed: bool

    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    cached_input_tokens: int | None
    reasoning_tokens: int | None
    estimated_cost_usd: float | None

    response_id: str | None
    finish_reason: str | None
    error_type: str | None
    error_message: str | None

    raw_response: str
    parsed_plan: dict[str, Any] | None
    wire_commands: list[list] | None

    task_success: bool | None
    safe: bool | None
    collision: bool | None
    boundary_violation: bool | None
    stop_reached: bool | None
    final_x_mm: float | None
    final_y_mm: float | None
    final_heading_deg: float | None
    position_error_mm: float | None
    heading_error_deg: float | None
    travel_distance_mm: float | None
    total_rotation_deg: float | None
    commands_executed: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
