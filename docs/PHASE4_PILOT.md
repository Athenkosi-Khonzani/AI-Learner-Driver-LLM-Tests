# Phase 4 - 30 × 3 × 4 Pilot Benchmark

## Experimental size

Phase 4 intentionally expands the pilot to:

- 30 frozen scenarios
- 3 repetitions of each scenario per model
- 4 model entries

Total:

```text
30 × 3 × 4 = 360 API calls
```

Each model therefore receives 90 trials.

This provides the first useful view of run-to-run non-determinism rather than
treating a single generation as representative of a model.

## Important cache-busting design

There is a tension between two goals:

1. test repeated planning under the same semantic task; and
2. avoid repeated-request prefix caching influencing latency.

Phase 4 changes **only** a neutral benchmark nonce at the beginning of the system
prompt:

```text
BENCHMARK NONCE: a1b2c3...
This identifier has no task meaning. Ignore it completely when planning...
```

The instruction, world state, command rules, coordinate conventions and structured
schema remain unchanged.

For each scenario/repetition pair, all four providers receive the **same nonce**.
A new nonce is used on the next repetition.

The result record stores both:

- `prompt_sha256`: hash of the canonical semantic prompt without the nonce
- `transmitted_prompt_sha256`: exact request hash including the nonce

This lets the report demonstrate that the task itself stayed fixed.

### Scientific wording

When reporting these repetitions, describe them as:

> repeated generations under an identical semantic planning task with a neutral
> cache-busting request nonce

rather than claiming the transmitted byte strings were literally identical.

## Randomization

At session creation:

- scenario/repetition pairs are shuffled,
- provider order is independently shuffled within every scenario/repetition,
- one reproducible random seed is stored in `session_plan.json`.

The frozen session plan therefore defines the exact experiment order before calls
begin.

## Server load protection

Calls are strictly sequential.

Default timing:

- 3–6 s randomized delay between requests
- an additional 15–25 s cooldown after each block of 40 calls
- no parallel API requests

The exact planned delay before every job is frozen in `session_plan.json`.

## Resume behavior

Each job has a unique ID:

```text
MULTI_04__r2__gemini_fast
```

A job is complete only after its individual JSON record exists.

If PowerShell closes, the network drops, or you press Ctrl+C:

```powershell
python run_phase4_pilot.py --resume-latest
```

The runner skips completed job IDs and continues the original frozen schedule.

No completed trial is repeated.

## API failures

There is no automatic retry.

An API failure is retained as the outcome of that trial. Automatically retrying a
failure would silently redefine one benchmark trial as "keep trying until the API
works."

## Safe first check

Before launching 360 paid calls:

```powershell
python run_phase4_pilot.py --dry-run
```

Then run only the first 8 real jobs:

```powershell
python run_phase4_pilot.py --resume-latest --limit 8
```

Inspect the records and summary. If correct:

```powershell
python run_phase4_pilot.py --resume-latest
```

## Outputs

Each Phase 4 session is self-contained:

```text
results/pilot/<session_id>/
├── session_plan.json
├── progress.json
├── records/
│   └── <one JSON file per API trial>
├── pilot_results.csv
├── pilot_results.jsonl
├── pilot_summary.json
├── pilot_summary.md
├── pilot_model_summary.csv
├── pilot_family_summary.csv
├── pilot_difficulty_summary.csv
└── pilot_scenario_consistency.csv
```

## Non-determinism metrics

For each model/scenario across the three repetitions:

- number of unique protocol-valid command plans
- modal plan fraction
- whether all three exact wire-command sequences are identical
- whether all three success/failure outcomes are identical
- whether all three repetitions succeeded

This separates plan variability from outcome variability. Two plans can differ while
both safely solve the same task.

## Latency statistics

Latency statistics are computed over protocol-valid executable plans:

- median
- P90
- P95

The primary metric remains plan-ready latency.

## Accuracy/safety statistics

The summary keeps distinct:

- task success rate
- protocol validity
- collision rate
- boundary violation rate
- position error
- family breakdown
- difficulty breakdown

No arbitrary combined score is introduced.
