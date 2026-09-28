# Phase 4 Result Visualisation and Replay

Phase 4 now has two independent ways to inspect the experiment:

1. statistical comparison plots across all completed API trials;
2. deterministic visual replay of the exact recorded command plans.

These tools do not make new API calls.

## Generate comparison plots

```powershell
python plot_phase4_results.py --session latest
```

Output:

```text
results/pilot/<session>/analysis/
├── ANALYSIS_SUMMARY.md
├── model_metrics.csv
├── family_metrics.csv
├── difficulty_metrics.csv
├── scenario_consistency.csv
├── failure_modes.csv
├── analysis_manifest.json
└── plots/
```

Standard plots:

1. Task success rate with 95% Wilson confidence intervals
2. Plan-ready latency distribution
3. API / schema / protocol reliability
4. Collision and boundary-violation rates
5. Success by scenario family
6. Success by difficulty D1/D2/D3
7. Final-position error distribution
8. Estimated API cost per call and per successful trial
9. Run-to-run repeatability / non-determinism
10. Executed command count
11. Travel distance
12. Total commanded rotation
13. Mutually exclusive trial outcome composition
14. Provider-reported cached-input observation, when available

The script works on partial sessions as well as the completed 360-call session.

## Replay the rover visually

```powershell
python replay_phase4_results.py --session latest
```

The replay GUI lets you choose model, scenario and repetition 1/2/3. It reloads the frozen scenario, reloads the exact LLM plan stored in the result, independently re-simulates it, checks the recomputed outcome against the stored benchmark result, and animates the rover path.

Controls include Play/Pause, Restart, Step, playback speed, trajectory overlay, PNG snapshot export and trajectory CSV export.

The white cross is the hidden evaluator target and was not sent to the LLM. The white trail is the replayed rover-centre trajectory.

## Batch replay verification

```powershell
python verify_phase4_replays.py --session latest
```

Every executable plan is independently re-simulated. The script checks task success, collision, boundary violation, STOP status and final pose. A clean audit should report:

```text
Replay mismatches: 0
```

## What visual replay proves

The replay demonstrates that the stored model plan produces the displayed trajectory in the deterministic benchmark simulator and that the stored score can be reproduced. It does not prove that a physical rover would follow exactly the same path; wheel slip, motor mismatch, perception error and real control feedback belong to the later physical-system experiment.
