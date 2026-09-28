# Phase 4 comparison summary

Completed trials analysed: **360**

| Model | Success | Protocol valid | Median latency ms | P95 ms | Collision | All 3 plans identical | Outcome consistent | Cost/call | Cost/success |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude Sonnet | 74.4% | 80.0% | 4109 | 5956 | 2.8% | 36.7% | 60.0% | $0.00560 | $0.00611 |
| Claude Haiku | 27.8% | 91.1% | 1648 | 2235 | 18.3% | 30.0% | 66.7% | $0.00165 | $0.00593 |
| Gemini Flash-Lite | 35.6% | 97.8% | 1426 | 2344 | 13.6% | 30.0% | 70.0% | $0.00059 | $0.00165 |
| OpenAI fast | 27.8% | 96.7% | 1617 | 2155 | 16.1% | 20.0% | 80.0% | $0.00012 | $0.00043 |

## Plot interpretation

- Success, schema validity and protocol validity are intentionally separate.
- Latency plots include only protocol-valid executable plans.
- Safety rates use trials that reached simulation.
- Exact-plan repeatability compares the compiled wire-command sequences.
- Outcome consistency can remain high even when exact command plans differ.
- Provider-reported cache metrics are observational and may not be reported by every API.
