from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path


def _rate(values) -> float | None:
    values = list(values)
    if not values:
        return None
    return sum(bool(v) for v in values) / len(values)


def _mean(values) -> float | None:
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return None
    return statistics.fmean(vals)


def _median(values) -> float | None:
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return None
    return statistics.median(vals)


def _percentile(values, p: float) -> float | None:
    vals = sorted(float(v) for v in values if v is not None)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]

    k = (len(vals) - 1) * p
    lo = math.floor(k)
    hi = math.ceil(k)

    if lo == hi:
        return vals[lo]

    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def _plan_key(record: dict) -> str | None:
    commands = record.get("wire_commands")
    if commands is None:
        return None
    return json.dumps(
        commands,
        sort_keys=False,
        separators=(",", ":"),
    )


def _load_records(session_dir: Path) -> list[dict]:
    records = []
    records_dir = session_dir / "records"

    for path in sorted(records_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        records.append(payload["record"])

    return records


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def generate_pilot_summary(
    session_dir: Path,
    session_plan: dict,
) -> dict:
    records = _load_records(session_dir)

    expected_repetitions = int(
        session_plan["repetitions_per_scenario"]
    )

    by_provider = defaultdict(list)
    by_provider_family = defaultdict(list)
    by_provider_difficulty = defaultdict(list)
    by_provider_scenario = defaultdict(list)

    for r in records:
        provider = r["provider_key"]
        by_provider[provider].append(r)
        by_provider_family[
            (provider, r.get("scenario_family"))
        ].append(r)
        by_provider_difficulty[
            (provider, r.get("scenario_difficulty"))
        ].append(r)
        by_provider_scenario[
            (provider, r["scenario_name"])
        ].append(r)

    scenario_consistency = []

    for (provider, scenario), rows in sorted(
        by_provider_scenario.items()
    ):
        rows = sorted(
            rows,
            key=lambda r: (
                r.get("repetition_index") or 0
            ),
        )

        valid_plan_keys = [
            _plan_key(r)
            for r in rows
            if r.get("protocol_valid")
            and _plan_key(r) is not None
        ]

        counts = Counter(valid_plan_keys)
        unique_valid_plans = len(counts)

        modal_fraction = None
        if valid_plan_keys:
            modal_fraction = (
                max(counts.values()) / len(valid_plan_keys)
            )

        completed_all_repetitions = (
            len(rows) == expected_repetitions
        )

        all_repetitions_identical = (
            completed_all_repetitions
            and len(valid_plan_keys) == expected_repetitions
            and unique_valid_plans == 1
        )

        success_values = [
            r.get("task_success")
            for r in rows
            if r.get("task_success") is not None
        ]

        outcome_consistent = (
            completed_all_repetitions
            and len(success_values) == expected_repetitions
            and len(set(success_values)) == 1
        )

        all_repetitions_successful = (
            completed_all_repetitions
            and len(success_values) == expected_repetitions
            and all(success_values)
        )

        scenario_consistency.append({
            "provider_key": provider,
            "scenario_name": scenario,
            "scenario_family": rows[0].get("scenario_family"),
            "scenario_difficulty": rows[0].get("scenario_difficulty"),
            "runs_completed": len(rows),
            "protocol_valid_runs": len(valid_plan_keys),
            "unique_valid_plans": unique_valid_plans,
            "modal_plan_fraction": modal_fraction,
            "all_repetitions_identical": all_repetitions_identical,
            "outcome_consistent": outcome_consistent,
            "all_repetitions_successful": all_repetitions_successful,
        })

    consistency_by_provider = defaultdict(list)
    for row in scenario_consistency:
        consistency_by_provider[
            row["provider_key"]
        ].append(row)

    provider_summary = []

    planned_counts = Counter(
        job["provider_key"]
        for job in session_plan["jobs"]
    )

    for provider, rows in sorted(by_provider.items()):
        valid_latency = [
            r["plan_ready_latency_ms"]
            for r in rows
            if r.get("protocol_valid")
        ]

        costs = [
            r["estimated_cost_usd"]
            for r in rows
            if r.get("estimated_cost_usd") is not None
        ]

        successes = [
            r for r in rows
            if r.get("task_success") is True
        ]

        consistency_rows = consistency_by_provider[provider]

        provider_summary.append({
            "provider_key": provider,
            "model": rows[0]["model"],
            "planned_calls": planned_counts[provider],
            "completed_calls": len(rows),

            "api_success_rate": _rate(
                r.get("api_success") for r in rows
            ),
            "schema_valid_rate": _rate(
                r.get("schema_valid") for r in rows
            ),
            "protocol_valid_rate": _rate(
                r.get("protocol_valid") for r in rows
            ),
            "task_success_rate": _rate(
                r.get("task_success") is True
                for r in rows
            ),

            "collision_rate_among_simulated": _rate(
                r.get("collision")
                for r in rows
                if r.get("simulation_executed")
            ),
            "boundary_violation_rate_among_simulated": _rate(
                r.get("boundary_violation")
                for r in rows
                if r.get("simulation_executed")
            ),

            "median_valid_plan_latency_ms": _median(
                valid_latency
            ),
            "p90_valid_plan_latency_ms": _percentile(
                valid_latency, 0.90
            ),
            "p95_valid_plan_latency_ms": _percentile(
                valid_latency, 0.95
            ),

            "mean_position_error_mm_simulated": _mean(
                r.get("position_error_mm")
                for r in rows
                if r.get("simulation_executed")
            ),
            "mean_travel_distance_mm_simulated": _mean(
                r.get("travel_distance_mm")
                for r in rows
                if r.get("simulation_executed")
            ),

            "total_estimated_cost_usd": sum(costs),
            "mean_estimated_cost_per_call_usd": _mean(costs),
            "estimated_cost_per_success_usd": (
                sum(costs) / len(successes)
                if successes else None
            ),

            # Non-determinism / repeatability.
            "mean_modal_plan_fraction": _mean(
                r.get("modal_plan_fraction")
                for r in consistency_rows
            ),
            "scenarios_all_3_plans_identical_rate": _rate(
                r.get("all_repetitions_identical")
                for r in consistency_rows
            ),
            "scenarios_outcome_consistent_rate": _rate(
                r.get("outcome_consistent")
                for r in consistency_rows
            ),
            "scenarios_all_3_successful_rate": _rate(
                r.get("all_repetitions_successful")
                for r in consistency_rows
            ),
        })

    family_summary = []
    for (provider, family), rows in sorted(
        by_provider_family.items()
    ):
        family_summary.append({
            "provider_key": provider,
            "family": family,
            "calls": len(rows),
            "task_success_rate": _rate(
                r.get("task_success") is True
                for r in rows
            ),
            "collision_rate_among_simulated": _rate(
                r.get("collision")
                for r in rows
                if r.get("simulation_executed")
            ),
            "median_valid_plan_latency_ms": _median(
                r.get("plan_ready_latency_ms")
                for r in rows
                if r.get("protocol_valid")
            ),
            "mean_position_error_mm_simulated": _mean(
                r.get("position_error_mm")
                for r in rows
                if r.get("simulation_executed")
            ),
        })

    difficulty_summary = []
    for (provider, difficulty), rows in sorted(
        by_provider_difficulty.items()
    ):
        difficulty_summary.append({
            "provider_key": provider,
            "difficulty": difficulty,
            "calls": len(rows),
            "task_success_rate": _rate(
                r.get("task_success") is True
                for r in rows
            ),
            "collision_rate_among_simulated": _rate(
                r.get("collision")
                for r in rows
                if r.get("simulation_executed")
            ),
            "median_valid_plan_latency_ms": _median(
                r.get("plan_ready_latency_ms")
                for r in rows
                if r.get("protocol_valid")
            ),
        })

    summary = {
        "pilot_version": session_plan["pilot_version"],
        "session_id": session_plan["session_id"],
        "seed": session_plan["seed"],
        "cache_busting_enabled": session_plan[
            "cache_busting_enabled"
        ],
        "planned_calls": len(session_plan["jobs"]),
        "completed_calls": len(records),
        "completion_rate": (
            len(records) / len(session_plan["jobs"])
            if session_plan["jobs"] else 0.0
        ),
        "provider_summary": provider_summary,
        "family_summary": family_summary,
        "difficulty_summary": difficulty_summary,
        "scenario_consistency": scenario_consistency,
    }

    (session_dir / "pilot_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    _write_csv(
        session_dir / "pilot_model_summary.csv",
        provider_summary,
    )
    _write_csv(
        session_dir / "pilot_family_summary.csv",
        family_summary,
    )
    _write_csv(
        session_dir / "pilot_difficulty_summary.csv",
        difficulty_summary,
    )
    _write_csv(
        session_dir / "pilot_scenario_consistency.csv",
        scenario_consistency,
    )

    _write_markdown(
        session_dir / "pilot_summary.md",
        summary,
    )

    return summary


def _fmt_pct(value):
    if value is None:
        return "n/a"
    return f"{100.0 * value:.1f}%"


def _fmt_num(value, digits=1):
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def _write_markdown(path: Path, summary: dict) -> None:
    lines = [
        "# Phase 4 Pilot Summary",
        "",
        f"- Session: `{summary['session_id']}`",
        f"- Seed: `{summary['seed']}`",
        f"- Calls: {summary['completed_calls']} / {summary['planned_calls']}",
        f"- Cache-busting nonce: {summary['cache_busting_enabled']}",
        "",
        "## Model summary",
        "",
        "| Model key | Task success | Protocol valid | Median latency (ms) | P90 (ms) | P95 (ms) | All 3 plans identical | Outcome consistent | Est. cost |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for row in summary["provider_summary"]:
        lines.append(
            "| "
            + " | ".join([
                str(row["provider_key"]),
                _fmt_pct(row["task_success_rate"]),
                _fmt_pct(row["protocol_valid_rate"]),
                _fmt_num(row["median_valid_plan_latency_ms"]),
                _fmt_num(row["p90_valid_plan_latency_ms"]),
                _fmt_num(row["p95_valid_plan_latency_ms"]),
                _fmt_pct(
                    row["scenarios_all_3_plans_identical_rate"]
                ),
                _fmt_pct(
                    row["scenarios_outcome_consistent_rate"]
                ),
                (
                    f"${row['total_estimated_cost_usd']:.4f}"
                    if row["total_estimated_cost_usd"] is not None
                    else "n/a"
                ),
            ])
            + " |"
        )

    lines.extend([
        "",
        "## Interpretation notes",
        "",
        "- Task success is kept separate from schema/protocol validity.",
        "- Latency statistics use protocol-valid executable plans.",
        "- 'All 3 plans identical' compares exact compiled wire-command sequences.",
        "- Outcome consistency asks whether all three repetitions had the same success/failure outcome, even if the command plans differed.",
        "- Cost values are estimates from the rates frozen in `benchmark_config.json`.",
        "",
    ])

    path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
