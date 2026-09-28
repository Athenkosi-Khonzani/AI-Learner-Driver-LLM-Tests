from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from llm_test.benchmark.output_models import StructuredPlan
from llm_test.benchmark.prompt_builder import build_prompt_payload
from llm_test.benchmark.benchmark_record import BenchmarkRecord
from llm_test.benchmark.result_store import ResultStore

from llm_test.commands.command_schema import (
    parse_plan,
    compile_wire_commands,
    CommandValidationError,
)

from llm_test.providers.openai_adapter import OpenAIAdapter
from llm_test.providers.anthropic_adapter import AnthropicAdapter
from llm_test.providers.gemini_adapter import GeminiAdapter

from llm_test.scenario.scenario_schema import Scenario
from llm_test.scenario.world_state_builder import build_world_state
from llm_test.simulator.rover_simulator import RoverSimulator
from llm_test.simulator.evaluator import evaluate


def _adapter_for(model_config: dict):
    provider = model_config["provider"]

    if provider == "openai":
        return OpenAIAdapter(model_config)

    if provider == "anthropic":
        return AnthropicAdapter(model_config)

    if provider == "gemini":
        return GeminiAdapter(model_config)

    raise ValueError(f"Unsupported provider: {provider}")


def _estimated_cost(
    input_tokens: int | None,
    output_tokens: int | None,
    model_config: dict,
) -> float | None:

    if input_tokens is None or output_tokens is None:
        return None

    input_rate = model_config.get("input_usd_per_million")
    output_rate = model_config.get("output_usd_per_million")

    if input_rate is None or output_rate is None:
        return None

    return (
        input_tokens * float(input_rate)
        + output_tokens * float(output_rate)
    ) / 1_000_000.0


def _sha256_prompt(payload: dict) -> str:
    value = (
        payload["system"]
        + "\n\n"
        + payload["user"]
    ).encode("utf-8")
    return hashlib.sha256(value).hexdigest()


class BenchmarkRunner:
    def __init__(
        self,
        project_root: Path,
        config: dict,
        session_id: str,
        store=None,
    ):
        self.project_root = project_root
        self.config = config
        self.store = store or ResultStore(
            project_root=project_root,
            session_id=session_id,
        )

    def run_one(
        self,
        scenario_path: Path,
        provider_key: str,
        run_index: int = 1,
        mode: str | None = None,
        benchmark_nonce: str | None = None,
        record_context: dict | None = None,
    ) -> BenchmarkRecord:

        scenario = Scenario.load(scenario_path)
        world_state = build_world_state(scenario)

        # Canonical prompt deliberately excludes the Phase 4 cache-busting nonce.
        canonical_prompt = build_prompt_payload(
            scenario.user_instruction,
            world_state,
            benchmark_nonce=None,
        )

        transmitted_prompt = build_prompt_payload(
            scenario.user_instruction,
            world_state,
            benchmark_nonce=benchmark_nonce,
        )

        canonical_prompt_hash = _sha256_prompt(canonical_prompt)
        transmitted_prompt_hash = _sha256_prompt(transmitted_prompt)

        mode = mode or self.config.get("mode", "structured")

        model_config = dict(
            self.config["models"][provider_key]
        )

        model_config.setdefault(
            "max_output_tokens",
            self.config.get("max_output_tokens", 512)
        )

        adapter = _adapter_for(model_config)

        response = adapter.generate(
            system_prompt=transmitted_prompt["system"],
            user_prompt=transmitted_prompt["user"],
            mode=mode,
        )

        validation_started = time.perf_counter()

        json_parse_success = response.parsed is not None
        schema_valid = False
        protocol_valid = False
        simulation_executed = False

        parsed_plan = response.parsed
        wire_commands = None

        score = None
        simulation = None

        error_type = response.error_type
        error_message = response.error_message

        if response.api_success and parsed_plan is not None:
            try:
                validated_model = StructuredPlan.model_validate(
                    parsed_plan
                )
                parsed_plan = validated_model.model_dump()
                schema_valid = True

                commands = parse_plan(parsed_plan)
                protocol_valid = True

                wire_commands = compile_wire_commands(
                    commands
                )

                simulation = RoverSimulator(
                    scenario
                ).simulate(commands)

                score = evaluate(
                    scenario,
                    simulation
                )

                simulation_executed = True

            except (
                ValidationError,
                CommandValidationError,
                ValueError,
                TypeError,
            ) as exc:
                error_type = type(exc).__name__
                error_message = str(exc)

        validation_latency_s = (
            time.perf_counter() - validation_started
        )

        usage = response.usage
        ctx = record_context or {}

        record = BenchmarkRecord(
            benchmark_version=self.config["benchmark_version"],
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            scenario_name=scenario.name,
            scenario_path=str(scenario_path),
            provider_key=provider_key,
            provider=response.provider,
            model=response.model,
            mode=mode,
            run_index=run_index,

            # Same across repetitions because the semantic task is frozen.
            prompt_sha256=canonical_prompt_hash,

            api_success=response.api_success,
            api_latency_ms=response.latency_s * 1000.0,
            validation_latency_ms=validation_latency_s * 1000.0,
            plan_ready_latency_ms=(
                response.latency_s + validation_latency_s
            ) * 1000.0,

            json_parse_success=json_parse_success,
            schema_valid=schema_valid,
            protocol_valid=protocol_valid,
            simulation_executed=simulation_executed,

            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            cached_input_tokens=usage.cached_input_tokens,
            reasoning_tokens=usage.reasoning_tokens,
            estimated_cost_usd=_estimated_cost(
                usage.input_tokens,
                usage.output_tokens,
                model_config,
            ),

            response_id=response.response_id,
            finish_reason=response.finish_reason,
            error_type=error_type,
            error_message=error_message,

            raw_response=response.raw_text,
            parsed_plan=parsed_plan,
            wire_commands=wire_commands,

            task_success=(
                score.task_success if score else None
            ),
            safe=(
                score.safe if score else None
            ),
            collision=(
                score.collision if score else None
            ),
            boundary_violation=(
                score.boundary_violation if score else None
            ),
            stop_reached=(
                score.stop_reached if score else None
            ),

            final_x_mm=(
                simulation.final_state.x_mm
                if simulation else None
            ),
            final_y_mm=(
                simulation.final_state.y_mm
                if simulation else None
            ),
            final_heading_deg=(
                simulation.final_state.heading_deg
                if simulation else None
            ),

            position_error_mm=(
                score.position_error_mm if score else None
            ),
            heading_error_deg=(
                score.heading_error_deg if score else None
            ),

            travel_distance_mm=(
                score.travel_distance_mm if score else None
            ),
            total_rotation_deg=(
                score.total_rotation_deg if score else None
            ),
            commands_executed=(
                score.commands_executed if score else None
            ),

            job_id=ctx.get("job_id"),
            scenario_family=ctx.get("scenario_family"),
            scenario_difficulty=ctx.get("scenario_difficulty"),
            scenario_title=ctx.get("scenario_title"),
            repetition_index=ctx.get("repetition_index"),
            execution_order=ctx.get("execution_order"),
            cache_buster_nonce=benchmark_nonce,
            transmitted_prompt_sha256=transmitted_prompt_hash,
        )

        request_payload = {
            "provider_key": provider_key,
            "provider": response.provider,
            "model": response.model,
            "mode": mode,

            # The transmitted request is logged exactly for reproducibility.
            "system_prompt": transmitted_prompt["system"],
            "user_prompt": transmitted_prompt["user"],

            "canonical_prompt_sha256": canonical_prompt_hash,
            "transmitted_prompt_sha256": transmitted_prompt_hash,
            "cache_buster_nonce": benchmark_nonce,

            "world_state": world_state,
            "user_instruction": scenario.user_instruction,

            # This is stored for audit/evaluation but never placed in the
            # transmitted model prompt.
            "hidden_goal_not_sent_to_model": scenario.hidden_goal.__dict__,
        }

        self.store.save_record(
            record,
            request_payload=request_payload,
        )

        self.store.append_csv(record)

        return record
