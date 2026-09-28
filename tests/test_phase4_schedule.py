import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_test.benchmark.phase4_batch_runner import (
    build_session_plan,
)


def _configs():
    benchmark = json.loads(
        (ROOT / "config" / "benchmark_config.json")
        .read_text(encoding="utf-8")
    )
    pilot = json.loads(
        (ROOT / "config" / "phase4_pilot_config.json")
        .read_text(encoding="utf-8")
    )
    return benchmark, pilot


def test_phase4_schedule_has_360_unique_jobs():
    benchmark, pilot = _configs()

    plan = build_session_plan(
        ROOT,
        benchmark,
        pilot,
        seed=4022,
        session_id="test_session",
    )

    assert len(plan["jobs"]) == 360

    job_ids = [j["job_id"] for j in plan["jobs"]]
    assert len(job_ids) == len(set(job_ids))

    counts = Counter(j["provider_key"] for j in plan["jobs"])
    assert counts == {
        "openai_fast": 90,
        "anthropic_fast": 90,
        "gemini_fast": 90,
        "anthropic_baseline": 90,
    }


def test_same_nonce_shared_across_models_per_scenario_repetition():
    benchmark, pilot = _configs()

    plan = build_session_plan(
        ROOT,
        benchmark,
        pilot,
        seed=1234,
        session_id="test_session",
    )

    grouped = defaultdict(list)

    for job in plan["jobs"]:
        grouped[
            (
                job["scenario_id"],
                job["repetition_index"],
            )
        ].append(job)

    assert len(grouped) == 90

    for jobs in grouped.values():
        assert len(jobs) == 4
        assert len(
            {j["benchmark_nonce"] for j in jobs}
        ) == 1


def test_three_repetitions_exist_for_every_scenario_provider():
    benchmark, pilot = _configs()

    plan = build_session_plan(
        ROOT,
        benchmark,
        pilot,
        seed=99,
        session_id="test_session",
    )

    grouped = defaultdict(set)

    for job in plan["jobs"]:
        grouped[
            (
                job["scenario_id"],
                job["provider_key"],
            )
        ].add(job["repetition_index"])

    assert len(grouped) == 30 * 4

    for reps in grouped.values():
        assert reps == {1, 2, 3}


def test_randomization_is_reproducible_from_seed():
    benchmark, pilot = _configs()

    a = build_session_plan(
        ROOT, benchmark, pilot,
        seed=2026,
        session_id="a",
    )
    b = build_session_plan(
        ROOT, benchmark, pilot,
        seed=2026,
        session_id="b",
    )

    sequence_a = [
        (
            j["scenario_id"],
            j["repetition_index"],
            j["provider_key"],
            j["benchmark_nonce"],
            j["pre_delay_seconds"],
        )
        for j in a["jobs"]
    ]

    sequence_b = [
        (
            j["scenario_id"],
            j["repetition_index"],
            j["provider_key"],
            j["benchmark_nonce"],
            j["pre_delay_seconds"],
        )
        for j in b["jobs"]
    ]

    assert sequence_a == sequence_b
