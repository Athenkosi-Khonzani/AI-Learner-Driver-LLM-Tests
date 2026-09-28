# Benchmark Summary

- Session: `20260928_051658_phase5_strong`
- Seed: `652694417`
- Calls: 180 / 180
- Cache-busting nonce: True

## Model summary

| Model key | Task success | Protocol valid | Median latency (ms) | P90 (ms) | P95 (ms) | All 3 plans identical | Outcome consistent | Est. cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| anthropic_strong | 98.3% | 100.0% | 6776.0 | 19473.8 | 22254.0 | 50.0% | 96.7% | $0.6417 |
| gemini_strong | 98.3% | 100.0% | 7425.2 | 11803.4 | 13862.4 | 66.7% | 96.7% | $0.1725 |
| openai_strong | 100.0% | 100.0% | 3840.8 | 6773.9 | 7354.3 | 76.7% | 100.0% | $0.2083 |

## Interpretation notes

- Task success is kept separate from schema/protocol validity.
- Latency statistics use protocol-valid executable plans.
- 'All repetitions identical' compares exact compiled wire-command sequences.
- Outcome consistency asks whether all three repetitions had the same success/failure outcome, even if the command plans differed.
- Cost values are estimates from the rates frozen in `benchmark_config.json`.
