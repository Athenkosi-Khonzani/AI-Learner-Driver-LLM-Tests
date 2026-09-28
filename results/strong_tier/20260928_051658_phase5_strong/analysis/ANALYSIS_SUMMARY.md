# Benchmark comparison summary

Completed trials analysed: **180**

| Model | Success | Protocol valid | Median latency ms | P95 ms | Collision | All 2 plans identical | Outcome consistent | Cost/call | Cost/success |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude Sonnet 5 | 98.3% | 100.0% | 6776 | 22254 | 1.7% | 50.0% | 96.7% | $0.01069 | $0.01088 |
| Gemini 3.1 Pro | 98.3% | 100.0% | 7425 | 13862 | 1.7% | 66.7% | 96.7% | $0.00288 | $0.00292 |
| GPT-6 Sol | 100.0% | 100.0% | 3841 | 7354 | 0.0% | 76.7% | 100.0% | $0.00347 | $0.00347 |

## Plot interpretation

- Success, schema validity and protocol validity are intentionally separate.
- Latency plots include only protocol-valid executable plans.
- Safety rates use trials that reached simulation.
- Exact-plan repeatability compares the compiled wire-command sequences.
- Outcome consistency can remain high even when exact command plans differ.
- Provider-reported cache metrics are observational and may not be reported by every API.
