from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import json
import math
import statistics


PROVIDER_LABELS = {
    "openai_fast": "OpenAI fast",
    "anthropic_fast": "Claude Haiku",
    "gemini_fast": "Gemini Flash-Lite",
    "anthropic_baseline": "Claude Sonnet",
    "openai_strong": "GPT-6 Sol",
    "anthropic_strong": "Claude Sonnet 5",
    "gemini_strong": "Gemini 3.1 Pro",
}


def provider_label(key: str) -> str:
    return PROVIDER_LABELS.get(key, key)


def resolve_session_dir(project_root: Path, session: str, group: str = "pilot") -> Path:
    session_root = project_root / "results" / group
    if session != "latest":
        path = session_root / session
        if not path.exists():
            raise FileNotFoundError(f"Benchmark session not found: {path}")
        return path
    if not session_root.exists():
        raise FileNotFoundError(f"No results/{group} directory exists yet.")
    candidates = [
        p for p in session_root.iterdir()
        if p.is_dir() and (p / "session_plan.json").exists()
    ]
    if not candidates:
        raise FileNotFoundError(f"No benchmark sessions were found under results/{group}.")
    return sorted(candidates, key=lambda p: p.name)[-1]


def load_records(session_dir: Path) -> list[dict[str, Any]]:
    records_dir = session_dir / "records"
    if not records_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(records_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        record = payload.get("record", payload)
        record["_record_path"] = str(path)
        rows.append(record)
    return rows


def mean(values) -> float | None:
    vals = [float(v) for v in values if v is not None]
    return statistics.fmean(vals) if vals else None


def median(values) -> float | None:
    vals = [float(v) for v in values if v is not None]
    return statistics.median(vals) if vals else None


def percentile(values, p: float) -> float | None:
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


def proportion(successes: int, total: int) -> float | None:
    return successes / total if total > 0 else None


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float | None, float | None]:
    """Return a numerically robust Wilson score interval.

    At an observed rate of exactly 0 or 1, floating-point roundoff can make
    the computed endpoint differ from the observed rate by ~1e-16.  That is
    statistically irrelevant but matplotlib rejects the resulting tiny
    negative error-bar length.  Clamp the interval so it always contains the
    observed proportion.
    """
    if total <= 0:
        return None, None

    p = successes / total
    z2 = z * z
    denom = 1.0 + z2 / total
    centre = (p + z2 / (2.0 * total)) / denom
    half = z * math.sqrt(
        p * (1.0 - p) / total
        + z2 / (4.0 * total * total)
    ) / denom

    low = max(0.0, centre - half)
    high = min(1.0, centre + half)

    # Numerical safety: the CI must contain the observed proportion.
    low = min(low, p)
    high = max(high, p)

    return low, high


def exact_plan_key(record: dict[str, Any]) -> str | None:
    commands = record.get("wire_commands")
    if commands is None:
        return None
    return json.dumps(commands, ensure_ascii=False, separators=(",", ":"))


def failure_mode(record: dict[str, Any]) -> str:
    if not record.get("api_success"):
        return "API failure"
    if not record.get("schema_valid"):
        return "Schema failure"
    if not record.get("protocol_valid"):
        return "Protocol failure"
    if record.get("collision"):
        return "Collision"
    if record.get("boundary_violation"):
        return "Boundary violation"
    if record.get("task_success") is True:
        return "Success"
    if record.get("simulation_executed"):
        return "Goal miss"
    return "Other"


def consistency_rows(records: list[dict[str, Any]], expected_repetitions: int = 3) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[(row["provider_key"], row["scenario_name"])].append(row)

    output: list[dict[str, Any]] = []
    for (provider, scenario), rows in sorted(grouped.items()):
        rows = sorted(rows, key=lambda r: int(r.get("repetition_index") or 0))
        plan_keys = [
            exact_plan_key(r) for r in rows
            if r.get("protocol_valid") and exact_plan_key(r) is not None
        ]
        counts = Counter(plan_keys)
        unique_plans = len(counts)
        modal_fraction = max(counts.values()) / len(plan_keys) if plan_keys else None
        success_values = [r.get("task_success") for r in rows if r.get("task_success") is not None]
        complete = len(rows) == expected_repetitions
        all_plans_identical = complete and len(plan_keys) == expected_repetitions and unique_plans == 1
        outcome_consistent = complete and len(success_values) == expected_repetitions and len(set(success_values)) == 1
        all_successful = complete and len(success_values) == expected_repetitions and all(success_values)
        output.append({
            "provider_key": provider,
            "scenario_name": scenario,
            "scenario_family": rows[0].get("scenario_family"),
            "scenario_difficulty": rows[0].get("scenario_difficulty"),
            "runs_completed": len(rows),
            "protocol_valid_runs": len(plan_keys),
            "unique_valid_plans": unique_plans,
            "modal_plan_fraction": modal_fraction,
            "all_repetitions_identical": all_plans_identical,
            "outcome_consistent": outcome_consistent,
            "all_repetitions_successful": all_successful,
        })
    return output


def model_metrics(records: list[dict[str, Any]], expected_repetitions: int = 3) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[row["provider_key"]].append(row)

    consistency = consistency_rows(records, expected_repetitions)
    by_consistency: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in consistency:
        by_consistency[row["provider_key"]].append(row)

    result = []
    for provider, rows in sorted(grouped.items()):
        total = len(rows)
        api_success = sum(r.get("api_success") is True for r in rows)
        schema_valid = sum(r.get("schema_valid") is True for r in rows)
        protocol_valid = sum(r.get("protocol_valid") is True for r in rows)
        task_success = sum(r.get("task_success") is True for r in rows)
        simulated = [r for r in rows if r.get("simulation_executed")]
        valid_latency = [r.get("plan_ready_latency_ms") for r in rows if r.get("protocol_valid")]
        costs = [r.get("estimated_cost_usd") for r in rows if r.get("estimated_cost_usd") is not None]
        crows = by_consistency.get(provider, [])

        def bool_rate(key: str) -> float | None:
            vals = [bool(r.get(key)) for r in crows]
            return sum(vals) / len(vals) if vals else None

        cache_reported_rows = [r for r in rows if r.get("cached_input_tokens") is not None]
        cache_hit_rate = None
        if cache_reported_rows:
            cache_hit_rate = sum((r.get("cached_input_tokens") or 0) > 0 for r in cache_reported_rows) / len(cache_reported_rows)

        lo, hi = wilson_interval(task_success, total)
        result.append({
            "provider_key": provider,
            "provider_label": provider_label(provider),
            "model": rows[0].get("model"),
            "trials": total,
            "api_success_rate": proportion(api_success, total),
            "schema_valid_rate": proportion(schema_valid, total),
            "protocol_valid_rate": proportion(protocol_valid, total),
            "task_success_rate": proportion(task_success, total),
            "task_success_ci_low": lo,
            "task_success_ci_high": hi,
            "collision_rate_simulated": proportion(sum(r.get("collision") is True for r in simulated), len(simulated)),
            "boundary_rate_simulated": proportion(sum(r.get("boundary_violation") is True for r in simulated), len(simulated)),
            "median_latency_ms": median(valid_latency),
            "p90_latency_ms": percentile(valid_latency, 0.90),
            "p95_latency_ms": percentile(valid_latency, 0.95),
            "mean_position_error_mm": mean(r.get("position_error_mm") for r in simulated),
            "median_position_error_mm": median(r.get("position_error_mm") for r in simulated),
            "mean_command_count": mean(r.get("commands_executed") for r in simulated),
            "mean_travel_distance_mm": mean(r.get("travel_distance_mm") for r in simulated),
            "mean_rotation_deg": mean(r.get("total_rotation_deg") for r in simulated),
            "mean_cost_usd": mean(costs),
            "total_cost_usd": sum(costs) if costs else None,
            "cost_per_success_usd": (sum(costs) / task_success if costs and task_success > 0 else None),
            "mean_modal_plan_fraction": mean(r.get("modal_plan_fraction") for r in crows),
            # Generic names are correct for both Phase 4 (3 repeats) and
            # Phase 5 (2 repeats).  Legacy all_3_* aliases are retained so
            # older analysis code continues to work.
            "all_repetitions_identical_rate": bool_rate("all_repetitions_identical"),
            "outcome_consistent_rate": bool_rate("outcome_consistent"),
            "all_repetitions_successful_rate": bool_rate("all_repetitions_successful"),
            "all_3_plans_identical_rate": bool_rate("all_repetitions_identical"),
            "all_3_successful_rate": bool_rate("all_repetitions_successful"),
            "reported_cache_hit_rate": cache_hit_rate,
            "mean_reported_cached_tokens": mean(r.get("cached_input_tokens") for r in cache_reported_rows),
        })
    return result


def family_metrics(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[(row["provider_key"], row.get("scenario_family") or "unknown")].append(row)
    out = []
    for (provider, family), rows in sorted(grouped.items()):
        total = len(rows)
        successes = sum(r.get("task_success") is True for r in rows)
        lo, hi = wilson_interval(successes, total)
        simulated = [r for r in rows if r.get("simulation_executed")]
        out.append({
            "provider_key": provider,
            "provider_label": provider_label(provider),
            "family": family,
            "trials": total,
            "task_success_rate": proportion(successes, total),
            "task_success_ci_low": lo,
            "task_success_ci_high": hi,
            "median_latency_ms": median(r.get("plan_ready_latency_ms") for r in rows if r.get("protocol_valid")),
            "collision_rate_simulated": proportion(sum(r.get("collision") is True for r in simulated), len(simulated)),
        })
    return out


def difficulty_metrics(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[(row["provider_key"], int(row.get("scenario_difficulty") or 0))].append(row)
    out = []
    for (provider, difficulty), rows in sorted(grouped.items()):
        total = len(rows)
        successes = sum(r.get("task_success") is True for r in rows)
        lo, hi = wilson_interval(successes, total)
        out.append({
            "provider_key": provider,
            "provider_label": provider_label(provider),
            "difficulty": difficulty,
            "trials": total,
            "task_success_rate": proportion(successes, total),
            "task_success_ci_low": lo,
            "task_success_ci_high": hi,
            "median_latency_ms": median(r.get("plan_ready_latency_ms") for r in rows if r.get("protocol_valid")),
        })
    return out


def failure_mode_metrics(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[row["provider_key"]].append(row)
    order = ["Success", "Goal miss", "Collision", "Boundary violation", "Protocol failure", "Schema failure", "API failure", "Other"]
    out = []
    for provider, rows in sorted(grouped.items()):
        counts = Counter(failure_mode(r) for r in rows)
        total = len(rows)
        row = {"provider_key": provider, "provider_label": provider_label(provider), "trials": total}
        for mode in order:
            row[mode] = counts[mode] / total if total else 0.0
        out.append(row)
    return out
