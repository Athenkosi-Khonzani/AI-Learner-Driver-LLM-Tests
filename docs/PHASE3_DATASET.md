
# Phase 3 - Frozen Benchmark Scenario Dataset

## Purpose

Phase 3 creates the fixed scenario dataset used to measure LLM planning accuracy,
safety, reliability, latency and cost.

No benchmark-model calls are made in this phase.

## Dataset

The frozen dataset contains 30 scenarios:

| Family | Count |
|---|---:|
| Basic motion | 4 |
| Coordinate navigation | 4 |
| Object-target navigation | 5 |
| Single-obstacle planning | 5 |
| Multi-obstacle planning | 6 |
| Tight/boundary planning | 6 |

Difficulty is stored separately from family:

- D1: direct/simple reasoning
- D2: moderate spatial planning
- D3: multi-step/tight-clearance planning

## Hidden goal separation

Each scenario file contains a hidden evaluator goal because the simulator needs an
objective target. The Phase 2 prompt builder sends only:

1. the natural-language user instruction, and
2. the generated world state.

The hidden evaluator goal is never included in the model prompt.

## Conservative feasibility proof

Every scenario is batch-checked by a conservative reference path validator.

The rover rectangle is enclosed by a circle whose radius is half of the rover
diagonal. Obstacles are inflated by that radius and arena boundaries are shrunk by
that radius. A grid A* search is then used only to confirm that a collision-free route
exists.

Because the circle contains the rover rectangle for every orientation, a successful
reference path is a conservative proof that the scenario is physically traversable
for the simulator rover.

The reference path is never shown to benchmark models and is not used to score them.

## Dataset lock

`dataset/benchmark_manifest.json` stores a SHA-256 checksum for every scenario.

Once benchmark collection begins:
- do not edit a scenario,
- do not edit its instruction,
- do not edit its hidden goal,
- do not change difficulty/family metadata.

Any change causes dataset validation to fail because the checksum no longer matches.

## Inspect

GUI:

```powershell
python run_dataset_manager.py
```

Batch validation:

```powershell
python validate_dataset.py
```
