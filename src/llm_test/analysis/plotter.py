from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from .core import (
    consistency_rows,
    difficulty_metrics,
    family_metrics,
    failure_mode_metrics,
    load_records,
    model_metrics,
    provider_label,
)

FAMILY_LABELS = {
    "basic_motion": "Basic motion",
    "coordinate_navigation": "Coordinate",
    "object_target": "Object target",
    "single_obstacle": "Single obstacle",
    "multi_obstacle": "Multi obstacle",
    "tight_boundary": "Tight/boundary",
}


def _pct(x):
    return 100.0 * x if x is not None else np.nan


def _save(fig, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _annotate_bar_percent(ax, bars):
    for bar in bars:
        height = bar.get_height()
        if np.isnan(height):
            continue
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            height,
            f"{height:.1f}%",
            ha="center",
            va="bottom",
            fontsize=8,
        )


def generate_all_plots(session_dir: Path, output_dir: Path | None = None) -> dict:
    records = load_records(session_dir)
    if not records:
        raise RuntimeError(f"No completed record files were found in {session_dir / 'records'}")

    output_dir = output_dir or (session_dir / "analysis")
    plots_dir = output_dir / "plots"
    output_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    expected_repetitions = 3
    session_plan_path = session_dir / "session_plan.json"
    if session_plan_path.exists():
        try:
            session_plan = json.loads(session_plan_path.read_text(encoding="utf-8"))
            expected_repetitions = int(session_plan.get("repetitions_per_scenario", 3))
        except Exception:
            expected_repetitions = 3

    model_rows = model_metrics(records, expected_repetitions=expected_repetitions)
    family_rows = family_metrics(records)
    diff_rows = difficulty_metrics(records)
    consistency = consistency_rows(records, expected_repetitions=expected_repetitions)
    failure_rows = failure_mode_metrics(records)

    _write_csv(output_dir / "model_metrics.csv", model_rows)
    _write_csv(output_dir / "family_metrics.csv", family_rows)
    _write_csv(output_dir / "difficulty_metrics.csv", diff_rows)
    _write_csv(output_dir / "scenario_consistency.csv", consistency)
    _write_csv(output_dir / "failure_modes.csv", failure_rows)

    providers = [row["provider_key"] for row in model_rows]
    labels = [row["provider_label"] for row in model_rows]
    x = np.arange(len(providers))
    generated = []

    # 01 task success + Wilson CI
    success = np.array([_pct(row["task_success_rate"]) for row in model_rows])
    ci_low = np.array([_pct(row["task_success_ci_low"]) for row in model_rows])
    ci_high = np.array([_pct(row["task_success_ci_high"]) for row in model_rows])
    # Floating-point roundoff at a perfect 0% or 100% success rate can
    # produce a value such as -2.2e-14 for one side of the error bar.
    # Matplotlib correctly rejects negative yerr values, so clamp numerical
    # noise to zero.  This does not alter the statistical interval.
    lower_err = np.maximum(0.0, success - ci_low)
    upper_err = np.maximum(0.0, ci_high - success)
    yerr = np.vstack([lower_err, upper_err])
    fig, ax = plt.subplots(figsize=(9, 5.4))
    bars = ax.bar(x, success, yerr=yerr, capsize=5)
    ax.set_title("Task success rate by model")
    ax.set_ylabel("Successful trials (%)")
    ax.set_xticks(x, labels, rotation=15, ha="right")
    ax.set_ylim(0, 105)
    ax.grid(axis="y", alpha=0.25)
    _annotate_bar_percent(ax, bars)
    path = plots_dir / "01_task_success_rate.png"
    _save(fig, path); generated.append(path)

    # 02 latency boxplot
    latency_by_provider = [
        [float(r["plan_ready_latency_ms"]) for r in records if r["provider_key"] == p and r.get("protocol_valid") and r.get("plan_ready_latency_ms") is not None]
        for p in providers
    ]
    fig, ax = plt.subplots(figsize=(9, 5.4))
    ax.boxplot(latency_by_provider, tick_labels=labels, showmeans=True)
    ax.set_title("Plan-ready latency distribution")
    ax.set_ylabel("Latency (ms)")
    ax.tick_params(axis="x", rotation=15)
    ax.grid(axis="y", alpha=0.25)
    path = plots_dir / "02_plan_ready_latency.png"
    _save(fig, path); generated.append(path)

    # 03 reliability grouped
    width = 0.23
    fig, ax = plt.subplots(figsize=(10, 5.6))
    metrics = [("api_success_rate", "API success"), ("schema_valid_rate", "Schema valid"), ("protocol_valid_rate", "Protocol valid")]
    for i, (key, label) in enumerate(metrics):
        vals = [_pct(row[key]) for row in model_rows]
        ax.bar(x + (i - 1) * width, vals, width, label=label)
    ax.set_title("Reliability of the model-to-command pipeline")
    ax.set_ylabel("Trials (%)")
    ax.set_xticks(x, labels, rotation=15, ha="right")
    ax.set_ylim(0, 105)
    ax.legend(); ax.grid(axis="y", alpha=0.25)
    path = plots_dir / "03_pipeline_reliability.png"
    _save(fig, path); generated.append(path)

    # 04 safety
    fig, ax = plt.subplots(figsize=(9, 5.4))
    width = 0.32
    collisions = [_pct(row["collision_rate_simulated"]) for row in model_rows]
    boundaries = [_pct(row["boundary_rate_simulated"]) for row in model_rows]
    ax.bar(x - width/2, collisions, width, label="Collision")
    ax.bar(x + width/2, boundaries, width, label="Boundary violation")
    ax.set_title("Safety failures among simulated plans")
    ax.set_ylabel("Simulated trials (%)")
    ax.set_xticks(x, labels, rotation=15, ha="right")
    ax.legend(); ax.grid(axis="y", alpha=0.25)
    path = plots_dir / "04_safety_failures.png"
    _save(fig, path); generated.append(path)

    # 05 success by family
    families = ["basic_motion", "coordinate_navigation", "object_target", "single_obstacle", "multi_obstacle", "tight_boundary"]
    family_lookup = {(r["provider_key"], r["family"]): r for r in family_rows}
    xf = np.arange(len(families)); width = 0.8 / max(1, len(providers))
    fig, ax = plt.subplots(figsize=(12, 6.2))
    for i, provider in enumerate(providers):
        vals = [_pct(family_lookup.get((provider, f), {}).get("task_success_rate")) for f in families]
        ax.bar(xf + (i - (len(providers)-1)/2) * width, vals, width, label=provider_label(provider))
    ax.set_title("Task success by scenario family")
    ax.set_ylabel("Successful trials (%)")
    ax.set_xticks(xf, [FAMILY_LABELS[f] for f in families], rotation=20, ha="right")
    ax.set_ylim(0, 105); ax.legend(); ax.grid(axis="y", alpha=0.25)
    path = plots_dir / "05_success_by_family.png"
    _save(fig, path); generated.append(path)

    # 06 success by difficulty
    difficulties = [1,2,3]
    diff_lookup = {(r["provider_key"], r["difficulty"]): r for r in diff_rows}
    xd = np.arange(len(difficulties)); width = 0.8 / max(1, len(providers))
    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    for i, provider in enumerate(providers):
        vals = [_pct(diff_lookup.get((provider, d), {}).get("task_success_rate")) for d in difficulties]
        ax.bar(xd + (i - (len(providers)-1)/2) * width, vals, width, label=provider_label(provider))
    ax.set_title("Task success by difficulty")
    ax.set_ylabel("Successful trials (%)")
    ax.set_xticks(xd, ["D1", "D2", "D3"])
    ax.set_ylim(0,105); ax.legend(); ax.grid(axis="y", alpha=0.25)
    path = plots_dir / "06_success_by_difficulty.png"
    _save(fig, path); generated.append(path)

    # 07 position error
    position_by_provider = [
        [float(r["position_error_mm"]) for r in records if r["provider_key"] == p and r.get("simulation_executed") and r.get("position_error_mm") is not None]
        for p in providers
    ]
    fig, ax = plt.subplots(figsize=(9,5.4))
    ax.boxplot(position_by_provider, tick_labels=labels, showmeans=True)
    ax.set_title("Final position error distribution")
    ax.set_ylabel("Position error (mm)")
    ax.tick_params(axis="x", rotation=15); ax.grid(axis="y", alpha=0.25)
    path = plots_dir / "07_position_error.png"
    _save(fig, path); generated.append(path)

    # 08 cost
    mean_cost = [row["mean_cost_usd"] or 0.0 for row in model_rows]
    success_cost = [row["cost_per_success_usd"] or 0.0 for row in model_rows]
    fig, ax = plt.subplots(figsize=(9,5.4)); width = 0.34
    ax.bar(x-width/2, mean_cost, width, label="Mean cost / call")
    ax.bar(x+width/2, success_cost, width, label="Estimated cost / success")
    ax.set_title("Estimated API cost"); ax.set_ylabel("USD")
    ax.set_xticks(x, labels, rotation=15, ha="right"); ax.legend(); ax.grid(axis="y", alpha=0.25)
    path = plots_dir / "08_cost_comparison.png"
    _save(fig, path); generated.append(path)

    # 09 repeatability
    fig, ax = plt.subplots(figsize=(10,5.7)); width = 0.23
    repeat_metrics = [
        (
            "all_repetitions_identical_rate",
            f"All {expected_repetitions} exact plans identical",
        ),
        ("outcome_consistent_rate", "Same success/failure outcome"),
        (
            "all_repetitions_successful_rate",
            f"All {expected_repetitions} repetitions successful",
        ),
    ]
    for i, (key,label) in enumerate(repeat_metrics):
        vals = [_pct(row[key]) for row in model_rows]
        ax.bar(x + (i-1)*width, vals, width, label=label)
    ax.set_title("Run-to-run repeatability across scenarios")
    ax.set_ylabel("Scenarios (%)")
    ax.set_xticks(x, labels, rotation=15, ha="right")
    ax.set_ylim(0,105); ax.legend(); ax.grid(axis="y", alpha=0.25)
    path = plots_dir / "09_repeatability.png"
    _save(fig, path); generated.append(path)

    # 10 command count
    command_by_provider = [
        [float(r["commands_executed"]) for r in records if r["provider_key"] == p and r.get("simulation_executed") and r.get("commands_executed") is not None]
        for p in providers
    ]
    fig, ax = plt.subplots(figsize=(9,5.4))
    ax.boxplot(command_by_provider, tick_labels=labels, showmeans=True)
    ax.set_title("Executed command count"); ax.set_ylabel("Commands")
    ax.tick_params(axis="x", rotation=15); ax.grid(axis="y", alpha=0.25)
    path = plots_dir / "10_command_count.png"
    _save(fig, path); generated.append(path)

    # 11 travel
    travel_by_provider = [
        [float(r["travel_distance_mm"]) for r in records if r["provider_key"] == p and r.get("simulation_executed") and r.get("travel_distance_mm") is not None]
        for p in providers
    ]
    fig, ax = plt.subplots(figsize=(9,5.4))
    ax.boxplot(travel_by_provider, tick_labels=labels, showmeans=True)
    ax.set_title("Travel distance distribution"); ax.set_ylabel("Travel distance (mm)")
    ax.tick_params(axis="x", rotation=15); ax.grid(axis="y", alpha=0.25)
    path = plots_dir / "11_travel_distance.png"
    _save(fig, path); generated.append(path)

    # 12 rotation
    rotation_by_provider = [
        [float(r["total_rotation_deg"]) for r in records if r["provider_key"] == p and r.get("simulation_executed") and r.get("total_rotation_deg") is not None]
        for p in providers
    ]
    fig, ax = plt.subplots(figsize=(9,5.4))
    ax.boxplot(rotation_by_provider, tick_labels=labels, showmeans=True)
    ax.set_title("Total commanded rotation"); ax.set_ylabel("Absolute rotation (degrees)")
    ax.tick_params(axis="x", rotation=15); ax.grid(axis="y", alpha=0.25)
    path = plots_dir / "12_total_rotation.png"
    _save(fig, path); generated.append(path)

    # 13 mutually-exclusive failure modes
    failure_order = ["Success", "Goal miss", "Collision", "Boundary violation", "Protocol failure", "Schema failure", "API failure", "Other"]
    failure_lookup = {r["provider_key"]: r for r in failure_rows}
    fig, ax = plt.subplots(figsize=(11,5.8)); bottom = np.zeros(len(providers))
    for mode in failure_order:
        vals = np.array([_pct(failure_lookup.get(p, {}).get(mode, 0.0)) for p in providers])
        ax.bar(x, vals, bottom=bottom, label=mode)
        bottom += vals
    ax.set_title("Trial outcome composition"); ax.set_ylabel("Trials (%)")
    ax.set_xticks(x, labels, rotation=15, ha="right"); ax.set_ylim(0,100)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01,1.0))
    path = plots_dir / "13_failure_mode_distribution.png"
    _save(fig, path); generated.append(path)

    # 14 cache observation (only if at least one provider reports it)
    if any(row["reported_cache_hit_rate"] is not None for row in model_rows):
        cache_rates = [_pct(row["reported_cache_hit_rate"]) if row["reported_cache_hit_rate"] is not None else 0.0 for row in model_rows]
        fig, ax = plt.subplots(figsize=(9,5.2))
        bars = ax.bar(x, cache_rates)
        ax.set_title("Provider-reported cached-input observations")
        ax.set_ylabel("Trials with cached_input_tokens > 0 (%)")
        ax.set_xticks(x, labels, rotation=15, ha="right"); ax.set_ylim(0,105)
        ax.grid(axis="y", alpha=0.25); _annotate_bar_percent(ax, bars)
        path = plots_dir / "14_reported_cache_observation.png"
        _save(fig, path); generated.append(path)

    summary = {
        "session": session_dir.name,
        "records_analyzed": len(records),
        "plots_generated": [str(p.relative_to(session_dir)) for p in generated],
    }
    (output_dir / "analysis_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _write_markdown_summary(output_dir / "ANALYSIS_SUMMARY.md", model_rows, len(records), expected_repetitions)
    return summary


def _fmt_pct(value):
    return "n/a" if value is None else f"{100*value:.1f}%"

def _fmt_ms(value):
    return "n/a" if value is None else f"{value:.0f}"

def _fmt_usd(value):
    return "n/a" if value is None else f"${value:.5f}"


def _write_markdown_summary(path: Path, rows: list[dict], record_count: int, expected_repetitions: int) -> None:
    lines = [
        "# Benchmark comparison summary", "",
        f"Completed trials analysed: **{record_count}**", "",
        f"| Model | Success | Protocol valid | Median latency ms | P95 ms | Collision | All {expected_repetitions} plans identical | Outcome consistent | Cost/call | Cost/success |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append("| " + " | ".join([
            row["provider_label"],
            _fmt_pct(row["task_success_rate"]),
            _fmt_pct(row["protocol_valid_rate"]),
            _fmt_ms(row["median_latency_ms"]),
            _fmt_ms(row["p95_latency_ms"]),
            _fmt_pct(row["collision_rate_simulated"]),
            _fmt_pct(row.get("all_repetitions_identical_rate", row["all_3_plans_identical_rate"])),
            _fmt_pct(row["outcome_consistent_rate"]),
            _fmt_usd(row["mean_cost_usd"]),
            _fmt_usd(row["cost_per_success_usd"]),
        ]) + " |")
    lines.extend([
        "", "## Plot interpretation", "",
        "- Success, schema validity and protocol validity are intentionally separate.",
        "- Latency plots include only protocol-valid executable plans.",
        "- Safety rates use trials that reached simulation.",
        "- Exact-plan repeatability compares the compiled wire-command sequences.",
        "- Outcome consistency can remain high even when exact command plans differ.",
        "- Provider-reported cache metrics are observational and may not be reported by every API.", "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")
