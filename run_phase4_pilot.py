from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from llm_test.benchmark.phase4_batch_runner import (
    build_session_plan,
    latest_incomplete_session,
    load_json,
    preflight_api_keys,
    run_session,
)


ALL_PROVIDERS = [
    "openai_fast",
    "anthropic_fast",
    "gemini_fast",
    "anthropic_baseline",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 4 pilot benchmark: 30 frozen scenarios x "
            "3 repetitions x 4 model entries."
        )
    )

    resume = parser.add_mutually_exclusive_group()
    resume.add_argument(
        "--session",
        help="Resume a specific Phase 4 session ID.",
    )
    resume.add_argument(
        "--resume-latest",
        action="store_true",
        help="Resume the newest incomplete Phase 4 session.",
    )

    parser.add_argument(
        "--providers",
        nargs="+",
        choices=ALL_PROVIDERS,
        default=None,
        help=(
            "Provider subset for a NEW session. "
            "Default: all four."
        ),
    )

    parser.add_argument(
        "--repetitions",
        type=int,
        default=None,
        help="Repetitions per scenario for a NEW session. Default: 3.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional reproducible randomization seed for a NEW session.",
    )

    parser.add_argument(
        "--no-cache-bust",
        action="store_true",
        help=(
            "Disable the neutral nonce. Not recommended for the "
            "planned Phase 4 dataset."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Run only the next N pending jobs this invocation. "
            "Useful for a small live check before the full pilot."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Create/show the randomized schedule but make no API calls.",
    )

    parser.add_argument(
        "--no-wait",
        action="store_true",
        help=(
            "Skip inter-call delays. Intended only for development "
            "with mocked APIs, not the real pilot."
        ),
    )

    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive RUN confirmation.",
    )

    args = parser.parse_args()

    benchmark_config = load_json(
        ROOT / "config" / "benchmark_config.json"
    )
    pilot_config = load_json(
        ROOT / "config" / "phase4_pilot_config.json"
    )

    pilot_root = ROOT / "results" / "pilot"
    pilot_root.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------
    # Resume existing session or create a new frozen schedule.
    # -------------------------------------------------------------
    if args.session:
        session_dir = pilot_root / args.session
        if not session_dir.exists():
            raise SystemExit(
                f"Session not found: {session_dir}"
            )
        plan = load_json(
            session_dir / "session_plan.json"
        )

    elif args.resume_latest:
        session_dir = latest_incomplete_session(
            pilot_root
        )
        if session_dir is None:
            raise SystemExit(
                "No incomplete Phase 4 session was found."
            )
        plan = load_json(
            session_dir / "session_plan.json"
        )

    else:
        plan = build_session_plan(
            project_root=ROOT,
            benchmark_config=benchmark_config,
            pilot_config=pilot_config,
            seed=args.seed,
            providers=args.providers,
            repetitions=args.repetitions,
            cache_busting_enabled=(
                not args.no_cache_bust
            ),
        )

        session_dir = (
            pilot_root / plan["session_id"]
        )
        session_dir.mkdir(
            parents=True,
            exist_ok=False,
        )

        (session_dir / "session_plan.json").write_text(
            json.dumps(plan, indent=2),
            encoding="utf-8",
        )

    provider_counts = {}
    for job in plan["jobs"]:
        provider_counts[job["provider_key"]] = (
            provider_counts.get(
                job["provider_key"], 0
            )
            + 1
        )

    delay_total = sum(
        float(job["pre_delay_seconds"])
        for job in plan["jobs"]
    )

    print()
    print("PHASE 4 PILOT PREFLIGHT")
    print("=" * 60)
    print(f"Session: {plan['session_id']}")
    print(f"Seed: {plan['seed']}")
    print(f"Dataset: {plan['dataset_version']}")
    print(f"Benchmark version: {plan['benchmark_version']}")
    print(
        f"Repetitions/scenario: "
        f"{plan['repetitions_per_scenario']}"
    )
    print(f"Total planned API calls: {len(plan['jobs'])}")
    print(f"Calls by model: {provider_counts}")
    print(
        f"Cache-busting nonce: "
        f"{plan['cache_busting_enabled']}"
    )
    print(
        "Scheduled inter-call/cooldown wait time: "
        f"{delay_total / 60.0:.1f} minutes "
        "(API response time is additional)"
    )
    print(
        "Execution is strictly sequential: "
        "parallel_calls = 1"
    )
    print()

    missing = preflight_api_keys(
        benchmark_config,
        plan["providers"],
    )

    if missing:
        print("MISSING API KEYS:")
        for item in missing:
            print(f"  - {item}")
        raise SystemExit(
            "Set the missing environment variable(s) before running."
        )

    print("First 12 randomized jobs:")
    for job in plan["jobs"][:12]:
        print(
            f"  {job['execution_order']:03d} "
            f"{job['scenario_id']} "
            f"r{job['repetition_index']} "
            f"{job['provider_key']} "
            f"wait={job['pre_delay_seconds']:.1f}s "
            f"nonce={job['benchmark_nonce']}"
        )

    print()

    if args.dry_run:
        print(
            "Dry run complete. No API calls were made.\n"
            f"Frozen schedule: "
            f"{session_dir / 'session_plan.json'}"
        )
        return

    if not args.yes:
        print(
            "This pilot can make up to "
            f"{len(plan['jobs'])} paid API calls."
        )
        confirmation = input(
            "Type RUN to begin/resume, or anything else to cancel: "
        ).strip()

        if confirmation != "RUN":
            print("Cancelled. The frozen session plan was kept.")
            return

    try:
        result = run_session(
            project_root=ROOT,
            session_dir=session_dir,
            plan=plan,
            benchmark_config=benchmark_config,
            limit=args.limit,
            no_wait=args.no_wait,
        )
    except KeyboardInterrupt:
        print(
            "\nInterrupted by user. Completed result files are safe.\n"
            "Resume with:\n"
            "  python run_phase4_pilot.py --resume-latest"
        )
        return

    progress = result["progress"]

    print()
    print("=" * 60)
    print("PHASE 4 INVOCATION COMPLETE")
    print(
        f"Completed: {progress['completed_calls']} / "
        f"{progress['planned_calls']}"
    )
    print(
        f"Remaining: {progress['remaining_calls']}"
    )
    print(
        f"Session directory: {session_dir}"
    )
    print(
        f"Summary: {session_dir / 'pilot_summary.md'}"
    )

    if progress["remaining_calls"] > 0:
        print(
            "\nResume later with:\n"
            "  python run_phase4_pilot.py --resume-latest"
        )


if __name__ == "__main__":
    main()
