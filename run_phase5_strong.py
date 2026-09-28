from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from llm_test.benchmark.phase5_batch_runner import (
    build_session_plan,
    latest_incomplete_session,
    load_json,
    preflight_api_keys,
    run_session,
)

ALL_PROVIDERS = [
    "openai_strong",
    "anthropic_strong",
    "gemini_strong",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 5 strong-tier benchmark: 30 frozen scenarios x "
            "2 repetitions x 3 strong models = 180 calls."
        )
    )
    resume = parser.add_mutually_exclusive_group()
    resume.add_argument("--session", help="Resume a specific Phase 5 session ID.")
    resume.add_argument("--resume-latest", action="store_true", help="Resume the newest incomplete strong-tier session.")
    parser.add_argument("--providers", nargs="+", choices=ALL_PROVIDERS, default=None)
    parser.add_argument("--repetitions", type=int, default=None, help="Default is 2.")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--no-cache-bust", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Run only the next N pending jobs.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-wait", action="store_true", help="Development only; not recommended for the real experiment.")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    benchmark_config = load_json(ROOT / "config" / "strong_tier_benchmark_config.json")
    pilot_config = load_json(ROOT / "config" / "phase5_strong_config.json")

    result_root = ROOT / "results" / "strong_tier"
    result_root.mkdir(parents=True, exist_ok=True)

    if args.session:
        session_dir = result_root / args.session
        if not session_dir.exists():
            raise SystemExit(f"Session not found: {session_dir}")
        plan = load_json(session_dir / "session_plan.json")
    elif args.resume_latest:
        session_dir = latest_incomplete_session(result_root)
        if session_dir is None:
            raise SystemExit("No incomplete Phase 5 strong-tier session was found.")
        plan = load_json(session_dir / "session_plan.json")
    else:
        plan = build_session_plan(
            project_root=ROOT,
            benchmark_config=benchmark_config,
            pilot_config=pilot_config,
            seed=args.seed,
            providers=args.providers,
            repetitions=args.repetitions,
            cache_busting_enabled=(not args.no_cache_bust),
        )
        session_dir = result_root / plan["session_id"]
        session_dir.mkdir(parents=True, exist_ok=False)
        (session_dir / "session_plan.json").write_text(json.dumps(plan,indent=2),encoding="utf-8")

    provider_counts = {}
    for job in plan["jobs"]:
        provider_counts[job["provider_key"]] = provider_counts.get(job["provider_key"],0)+1

    delay_total = sum(float(job["pre_delay_seconds"]) for job in plan["jobs"])

    print("\nPHASE 5 STRONG-TIER PREFLIGHT")
    print("="*64)
    print(f"Session: {plan['session_id']}")
    print(f"Seed: {plan['seed']}")
    print(f"Repetitions/scenario: {plan['repetitions_per_scenario']}")
    print(f"Total planned API calls: {len(plan['jobs'])}")
    print(f"Calls by model: {provider_counts}")
    print(f"Cache-busting nonce: {plan['cache_busting_enabled']}")
    print(f"Scheduled wait time: {delay_total/60.0:.1f} minutes (API latency additional)")
    print("Reasoning condition: medium for all three model families")
    print("Output limit: 8192 tokens per call (actual usage, not the limit, drives token cost)")
    print("Execution: sequential only\n")

    missing = preflight_api_keys(benchmark_config, plan["providers"])
    if missing:
        print("MISSING API KEYS:")
        for item in missing: print(f"  - {item}")
        raise SystemExit("Set missing environment variable(s) before running.")

    print("First 10 randomized jobs:")
    for job in plan["jobs"][:10]:
        print(
            f"  {job['execution_order']:03d} {job['scenario_id']} "
            f"r{job['repetition_index']} {job['provider_key']} "
            f"wait={job['pre_delay_seconds']:.1f}s nonce={job['benchmark_nonce']}"
        )
    print()

    if args.dry_run:
        print("Dry run complete. No API calls were made.")
        print(f"Frozen schedule: {session_dir / 'session_plan.json'}")
        return

    if not args.yes:
        print(f"This experiment can make up to {len(plan['jobs'])} paid API calls.")
        confirmation = input("Type RUN to begin/resume, or anything else to cancel: ").strip()
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
        print("\nInterrupted. Completed records are safe.")
        print("Resume with: python run_phase5_strong.py --resume-latest")
        return

    progress = result["progress"]
    print("\n" + "="*64)
    print(f"Completed: {progress['completed_calls']} / {progress['planned_calls']}")
    print(f"Remaining: {progress['remaining_calls']}")
    print(f"Session: {session_dir}")
    print(f"Summary: {session_dir / 'pilot_summary.md'}")
    if progress["remaining_calls"] > 0:
        print("Resume with: python run_phase5_strong.py --resume-latest")


if __name__ == "__main__":
    main()
