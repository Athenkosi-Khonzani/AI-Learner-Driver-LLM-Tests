# Phase 4 Pilot Summary

- Session: `20260928_021535_phase4`
- Seed: `1034991309`
- Calls: 360 / 360
- Cache-busting nonce: True

## Model summary

| Model key | Task success | Protocol valid | Median latency (ms) | P90 (ms) | P95 (ms) | All 3 plans identical | Outcome consistent | Est. cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| anthropic_baseline | 74.4% | 80.0% | 4108.8 | 5607.0 | 5956.2 | 36.7% | 60.0% | $0.4091 |
| anthropic_fast | 27.8% | 91.1% | 1648.1 | 2065.8 | 2235.3 | 30.0% | 66.7% | $0.1482 |
| gemini_fast | 35.6% | 97.8% | 1425.6 | 2255.3 | 2343.8 | 30.0% | 70.0% | $0.0529 |
| openai_fast | 27.8% | 96.7% | 1616.6 | 1869.2 | 2154.5 | 20.0% | 80.0% | $0.0107 |

## Interpretation notes

- Task success is kept separate from schema/protocol validity.
- Latency statistics use protocol-valid executable plans.
- 'All 3 plans identical' compares exact compiled wire-command sequences.
- Outcome consistency asks whether all three repetitions had the same success/failure outcome, even if the command plans differed.
- Cost values are estimates from the rates frozen in `benchmark_config.json`.
