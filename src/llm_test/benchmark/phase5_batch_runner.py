from __future__ import annotations

import hashlib
import json
import os
import random
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from llm_test.benchmark.benchmark_runner import BenchmarkRunner
from llm_test.benchmark.pilot_store import PilotResultStore
from llm_test.benchmark.pilot_summary import generate_pilot_summary
from llm_test.dataset.validator import validate_manifest


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _session_id_now() -> str:
    return datetime.now().strftime(
        "%Y%m%d_%H%M%S_phase5_strong"
    )


def _nonce(rng: random.Random) -> str:
    return f"{rng.getrandbits(64):016x}"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_session_plan(
    project_root: Path,
    benchmark_config: dict,
    pilot_config: dict,
    seed: int | None = None,
    providers: list[str] | None = None,
    repetitions: int | None = None,
    cache_busting_enabled: bool | None = None,
    session_id: str | None = None,
) -> dict:

    dataset_report = validate_manifest(project_root)
    if not dataset_report["all_valid"]:
        raise RuntimeError(
            "Frozen dataset validation failed. Run validate_dataset.py "
            "and do not benchmark until every scenario passes."
        )

    manifest_path = (
        project_root
        / "dataset"
        / "benchmark_manifest.json"
    )
    benchmark_config_path = (
        project_root
        / "config"
        / "strong_tier_benchmark_config.json"
    )
    pilot_config_path = (
        project_root
        / "config"
        / "phase5_strong_config.json"
    )

    manifest = load_json(manifest_path)

    providers = providers or list(
        pilot_config["providers"]
    )
    repetitions = (
        repetitions
        if repetitions is not None
        else int(
            pilot_config["repetitions_per_scenario"]
        )
    )

    if repetitions < 1:
        raise ValueError(
            "repetitions must be >= 1"
        )

    for provider in providers:
        if provider not in benchmark_config["models"]:
            raise ValueError(
                f"Unknown provider key: {provider}"
            )

    if cache_busting_enabled is None:
        cache_busting_enabled = bool(
            pilot_config["cache_busting"]["enabled"]
        )

    if seed is None:
        seed = random.SystemRandom().randrange(
            1, 2**31
        )

    rng = random.Random(seed)

    scenario_repetitions = []
    for entry in manifest["scenarios"]:
        for repetition in range(1, repetitions + 1):
            scenario_repetitions.append(
                (entry, repetition)
            )

    if pilot_config["scheduling"].get(
        "randomize_scenario_repetition_order",
        True,
    ):
        rng.shuffle(scenario_repetitions)

    jobs = []
    execution_order = 0

    delay_min = float(
        pilot_config["scheduling"][
            "delay_min_seconds"
        ]
    )
    delay_max = float(
        pilot_config["scheduling"][
            "delay_max_seconds"
        ]
    )
    cooldown_every = int(
        pilot_config["scheduling"][
            "cooldown_every_calls"
        ]
    )
    cooldown_min = float(
        pilot_config["scheduling"][
            "cooldown_min_seconds"
        ]
    )
    cooldown_max = float(
        pilot_config["scheduling"][
            "cooldown_max_seconds"
        ]
    )

    for entry, repetition in scenario_repetitions:
        pair_nonce = (
            _nonce(rng)
            if cache_busting_enabled
            else None
        )

        provider_order = list(providers)

        if pilot_config["scheduling"].get(
            "randomize_provider_order_within_repetition",
            True,
        ):
            rng.shuffle(provider_order)

        for provider_key in provider_order:
            execution_order += 1

            pre_delay = (
                0.0
                if execution_order == 1
                else rng.uniform(delay_min, delay_max)
            )

            if (
                cooldown_every > 0
                and execution_order > 1
                and (execution_order - 1) % cooldown_every == 0
            ):
                pre_delay += rng.uniform(
                    cooldown_min,
                    cooldown_max,
                )

            job_id = (
                f"{entry['id']}__"
                f"r{repetition}__"
                f"{provider_key}"
            )

            jobs.append({
                "job_id": job_id,
                "execution_order": execution_order,
                "scenario_id": entry["id"],
                "scenario_file": entry["file"],
                "scenario_family": entry["family"],
                "scenario_difficulty": entry["difficulty"],
                "scenario_title": entry["title"],
                "provider_key": provider_key,
                "model": benchmark_config[
                    "models"
                ][provider_key]["model"],
                "repetition_index": repetition,
                "benchmark_nonce": pair_nonce,
                "pre_delay_seconds": round(
                    pre_delay, 3
                ),
            })

    session_id = session_id or _session_id_now()

    return {
        "pilot_version": pilot_config[
            "pilot_version"
        ],
        "session_id": session_id,
        "created_utc": _utc_now(),
        "seed": seed,
        "mode": pilot_config["mode"],
        "repetitions_per_scenario": repetitions,
        "providers": providers,
        "cache_busting_enabled": cache_busting_enabled,
        "scheduling": pilot_config["scheduling"],

        # Freeze exact inputs/configs for resume integrity.
        "dataset_manifest_sha256": _sha256_file(
            manifest_path
        ),
        "benchmark_config_sha256": _sha256_file(
            benchmark_config_path
        ),
        "pilot_config_sha256": _sha256_file(
            pilot_config_path
        ),
        "dataset_version": manifest[
            "dataset_version"
        ],
        "benchmark_version": benchmark_config[
            "benchmark_version"
        ],

        "jobs": jobs,
    }


def verify_session_inputs(
    project_root: Path,
    plan: dict,
) -> None:
    files = {
        "dataset_manifest_sha256": (
            project_root
            / "dataset"
            / "benchmark_manifest.json"
        ),
        "benchmark_config_sha256": (
            project_root
            / "config"
            / "strong_tier_benchmark_config.json"
        ),
        "pilot_config_sha256": (
            project_root
            / "config"
            / "phase5_strong_config.json"
        ),
    }

    mismatches = []

    for key, path in files.items():
        actual = _sha256_file(path)
        if actual != plan[key]:
            mismatches.append(
                f"{path.name}: expected {plan[key]}, got {actual}"
            )

    if mismatches:
        raise RuntimeError(
            "Phase 5 strong-tier session cannot resume because frozen inputs changed:\n"
            + "\n".join(mismatches)
        )


def write_progress(
    session_dir: Path,
    plan: dict,
    store: PilotResultStore,
) -> dict:
    completed = store.completed_job_ids()
    total = len(plan["jobs"])

    by_provider_planned = Counter(
        j["provider_key"] for j in plan["jobs"]
    )

    by_provider_complete = Counter()
    for job in plan["jobs"]:
        if job["job_id"] in completed:
            by_provider_complete[
                job["provider_key"]
            ] += 1

    progress = {
        "session_id": plan["session_id"],
        "updated_utc": _utc_now(),
        "planned_calls": total,
        "completed_calls": len(completed),
        "remaining_calls": total - len(completed),
        "completion_fraction": (
            len(completed) / total
            if total else 0.0
        ),
        "planned_by_provider": dict(
            by_provider_planned
        ),
        "completed_by_provider": dict(
            by_provider_complete
        ),
    }

    (session_dir / "progress.json").write_text(
        json.dumps(progress, indent=2),
        encoding="utf-8",
    )

    return progress


def latest_incomplete_session(
    pilot_root: Path,
) -> Path | None:
    candidates = []

    if not pilot_root.exists():
        return None

    for session_dir in pilot_root.iterdir():
        if not session_dir.is_dir():
            continue

        plan_path = session_dir / "session_plan.json"
        if not plan_path.exists():
            continue

        plan = load_json(plan_path)
        store = PilotResultStore(session_dir)

        if len(store.completed_job_ids()) < len(
            plan["jobs"]
        ):
            candidates.append(session_dir)

    if not candidates:
        return None

    return sorted(
        candidates,
        key=lambda p: p.name,
        reverse=True,
    )[0]


def preflight_api_keys(
    benchmark_config: dict,
    providers: list[str],
) -> list[str]:
    missing = []

    for provider in providers:
        env_name = benchmark_config[
            "models"
        ][provider]["api_key_env"]

        if not os.getenv(env_name):
            missing.append(
                f"{provider} -> {env_name}"
            )

    return missing


def run_session(
    project_root: Path,
    session_dir: Path,
    plan: dict,
    benchmark_config: dict,
    *,
    limit: int | None = None,
    no_wait: bool = False,
) -> dict:

    verify_session_inputs(
        project_root,
        plan,
    )

    store = PilotResultStore(session_dir)

    runner = BenchmarkRunner(
        project_root=project_root,
        config=benchmark_config,
        session_id=plan["session_id"],
        store=store,
    )

    completed = store.completed_job_ids()
    pending = [
        job
        for job in plan["jobs"]
        if job["job_id"] not in completed
    ]

    if limit is not None:
        pending = pending[:limit]

    print(
        f"Session: {plan['session_id']}\n"
        f"Seed: {plan['seed']}\n"
        f"Completed before this run: "
        f"{len(completed)} / {len(plan['jobs'])}\n"
        f"Calls scheduled this invocation: {len(pending)}\n"
    )

    for local_index, job in enumerate(
        pending,
        start=1,
    ):
        delay = float(
            job["pre_delay_seconds"]
        )

        if delay > 0 and not no_wait:
            print(
                f"[{local_index}/{len(pending)}] "
                f"waiting {delay:.1f}s before next API call..."
            )
            time.sleep(delay)

        print(
            f"[{local_index}/{len(pending)}] "
            f"global {job['execution_order']}/{len(plan['jobs'])} | "
            f"{job['scenario_id']} r{job['repetition_index']} | "
            f"{job['provider_key']} ({job['model']})"
        )

        scenario_path = (
            project_root
            / "dataset"
            / job["scenario_file"]
        )

        record = runner.run_one(
            scenario_path=scenario_path,
            provider_key=job["provider_key"],
            run_index=job["execution_order"],
            mode=plan["mode"],
            benchmark_nonce=job[
                "benchmark_nonce"
            ],
            record_context={
                "job_id": job["job_id"],
                "scenario_family": job[
                    "scenario_family"
                ],
                "scenario_difficulty": job[
                    "scenario_difficulty"
                ],
                "scenario_title": job[
                    "scenario_title"
                ],
                "repetition_index": job[
                    "repetition_index"
                ],
                "execution_order": job[
                    "execution_order"
                ],
            },
        )

        print(
            "  "
            f"api={record.api_success} "
            f"schema={record.schema_valid} "
            f"protocol={record.protocol_valid} "
            f"success={record.task_success} "
            f"latency={record.plan_ready_latency_ms:.1f} ms "
            f"cost="
            + (
                f"${record.estimated_cost_usd:.6f}"
                if record.estimated_cost_usd is not None
                else "n/a"
            )
        )

        if record.error_message:
            print(
                f"  ERROR {record.error_type}: "
                f"{record.error_message}"
            )

        write_progress(
            session_dir,
            plan,
            store,
        )

        # Generate an incremental summary after every call. This means Ctrl+C
        # still leaves a readable partial report.
        generate_pilot_summary(
            session_dir,
            plan,
        )

    progress = write_progress(
        session_dir,
        plan,
        store,
    )

    summary = generate_pilot_summary(
        session_dir,
        plan,
    )

    return {
        "progress": progress,
        "summary": summary,
    }
