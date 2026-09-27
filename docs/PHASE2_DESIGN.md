# Phase 2 - Provider Benchmark Infrastructure

Phase 2 remains completely independent from `ai_learner_host`.

## First goal

Before spending meaningful credits, perform exactly one request per provider on one
simple saved scenario.

Default smoke-test models frozen on 2026-09-27:

- OpenAI fast: `gpt-6-luna`, reasoning effort `none`
- Anthropic fast: `claude-haiku-4-5-20251001`, thinking off/default
- Google fast: `gemini-3.5-flash-lite`, thinking level `minimal`
- Anthropic capability baseline: `claude-sonnet-5`, adaptive thinking, effort `low`

All IDs and settings are stored in `config/benchmark_config.json`.

## Benchmark modes

### structured

Uses each provider's native schema-constrained structured-output mechanism.

This is the production-oriented benchmark.

### prompt_only

No provider-native structured output is requested. The same system prompt tells the
model to return the command structure, and the benchmark attempts to parse the result.

This is the later formatting stress test.

## Primary latency metric

`plan_ready_latency_ms` = complete API response latency + local schema/protocol
validation latency.

The rover cannot safely execute an incomplete response, so time-to-first-token is not
the primary metric.

## Stored records

Each attempt records:

- provider + exact model ID
- mode
- API latency
- validation latency
- plan-ready latency
- token usage
- estimated standard token cost
- raw model response
- parsed plan
- compiled rover wire commands
- protocol validity
- simulation results
- objective hidden-goal evaluation

API keys are read only from environment variables and are never written to benchmark
records.
