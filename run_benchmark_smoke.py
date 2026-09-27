\
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from llm_test.benchmark.benchmark_runner import BenchmarkRunner


DEFAULT_PROVIDERS = [
    "openai_fast",
    "anthropic_fast",
    "gemini_fast",
    "anthropic_baseline",
]


def key_status(config: dict, provider_keys: list[str]) -> None:
    print("API key status:")
    for key in provider_keys:
        env_name = config["models"][key]["api_key_env"]
        present = bool(os.getenv(env_name))
        print(
            f"  {key:20s} {env_name:20s} "
            f"{'OK' if present else 'MISSING'}"
        )
    print()


def print_record(record) -> None:
    print(
        f"{record.provider_key:20s} | "
        f"{record.model:30s} | "
        f"api={record.api_success!s:5s} | "
        f"schema={record.schema_valid!s:5s} | "
        f"protocol={record.protocol_valid!s:5s} | "
        f"success={str(record.task_success):5s} | "
        f"latency={record.plan_ready_latency_ms:8.1f} ms"
    )

    if record.estimated_cost_usd is not None:
        print(
            f"  tokens in/out: "
            f"{record.input_tokens}/{record.output_tokens} | "
            f"estimated cost: ${record.estimated_cost_usd:.6f}"
        )

    if record.error_message:
        print(
            f"  ERROR {record.error_type}: "
            f"{record.error_message}"
        )

    if record.wire_commands is not None:
        print(
            "  wire commands: "
            + json.dumps(record.wire_commands)
        )

    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "One-scenario Phase 2 smoke benchmark. "
            "Calls each selected provider once."
        )
    )

    parser.add_argument(
        "--scenario",
        default=(
            "scenarios/basic/"
            "phase2_smoke_coordinate_target.json"
        ),
    )

    parser.add_argument(
        "--providers",
        nargs="+",
        default=DEFAULT_PROVIDERS,
        choices=DEFAULT_PROVIDERS,
    )

    parser.add_argument(
        "--mode",
        choices=["structured", "prompt_only"],
        default="structured",
    )

    args = parser.parse_args()

    config_path = ROOT / "config" / "benchmark_config.json"
    config = json.loads(
        config_path.read_text(encoding="utf-8")
    )

    scenario_path = ROOT / args.scenario

    if not scenario_path.exists():
        raise SystemExit(
            f"Scenario does not exist: {scenario_path}"
        )

    key_status(config, args.providers)

    missing = [
        key
        for key in args.providers
        if not os.getenv(
            config["models"][key]["api_key_env"]
        )
    ]

    if missing:
        print(
            "One or more selected providers are missing an API key "
            "in this process. The benchmark will still run and will "
            "record those calls as API failures."
        )
        print()

    session_id = time.strftime(
        "%Y%m%d_%H%M%S_smoke"
    )

    runner = BenchmarkRunner(
        project_root=ROOT,
        config=config,
        session_id=session_id,
    )

    print(
        f"Scenario: {scenario_path.name}\n"
        f"Mode: {args.mode}\n"
        f"Session: {session_id}\n"
    )

    for index, provider_key in enumerate(
        args.providers,
        start=1,
    ):
        print(
            f"Running {provider_key} "
            f"({index}/{len(args.providers)})..."
        )

        record = runner.run_one(
            scenario_path=scenario_path,
            provider_key=provider_key,
            run_index=index,
            mode=args.mode,
        )

        print_record(record)

    print("Smoke benchmark complete.")
    print(
        f"Raw session records: "
        f"{ROOT / 'results' / 'raw' / session_id}"
    )
    print(
        f"CSV: "
        f"{ROOT / 'results' / 'processed' / 'benchmark_results.csv'}"
    )
    print(
        f"JSONL: "
        f"{ROOT / 'results' / 'processed' / 'benchmark_results.jsonl'}"
    )


if __name__ == "__main__":
    main()
