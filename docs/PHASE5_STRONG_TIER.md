# Phase 5 - Strong-tier cross-provider benchmark

## Research question

After Phase 4 showed a substantial spatial-planning accuracy gap between fast models and Claude Sonnet 5, Phase 5 compares similarly priced stronger reasoning models from three providers on the **same frozen 30-scenario dataset**.

## Models and frozen settings (28 Sep 2026)

| Provider | Model ID | Reasoning setting | Standard token price used for estimates |
|---|---|---|---|
| OpenAI | `gpt-6-sol` | medium | $2/M input, $10/M output |
| Anthropic | `claude-sonnet-5` | adaptive thinking, medium effort | $2/M input, $10/M output |
| Google | `gemini-3.1-pro-preview` | medium thinking | $2/M input, $12/M output for prompts under 200k tokens |

Gemini 3.1 Pro is a preview model. Exact model IDs and the benchmark date are stored for reproducibility.

## Experimental size

```text
30 scenarios × 2 repetitions × 3 models = 180 API calls
60 trials per model
```

Two repetitions reduce cost while still allowing a direct check of whether the exact same semantic task produces the same command plan twice. This is weaker evidence about non-determinism than Phase 4's three repetitions, so repeatability results should be described as **two-run agreement**, not a full variance estimate.

## Fairness controls

- Same frozen Phase 3 scenarios and hidden evaluator goals.
- Same prompt semantics and command schema.
- Same neutral cache-busting nonce shared by all three providers within a scenario/repetition pair.
- Reasoning setting fixed to `medium` for all three model families where the provider supports that level.
- Calls are sequential and provider order is randomized.
- 4-7 s inter-call delay plus periodic cooldowns.
- No automatic retry.

## Sonnet parsing fix

Phase 4 used only 512 max output tokens while Sonnet 5 had adaptive thinking enabled. Anthropic documents `max_tokens` as a hard limit across thinking plus answer text. Phase 5 raises the limit to **8192 tokens**; billing remains based on actual generated tokens, not the configured maximum. The adapter also now distinguishes a successful API response from a subsequent JSON parsing failure, so parser failures are no longer mislabeled as API outages.

The same 8192 output ceiling is configured for the OpenAI and Gemini strong-tier calls.

## Run sequence

Create the frozen randomized schedule without spending credits:

```powershell
python run_phase5_strong.py --dry-run
```

Then make a small six-call check (two scenario/repetition/provider groups may be represented depending on randomized order):

```powershell
python run_phase5_strong.py --resume-latest --limit 6
```

Inspect the records, then continue:

```powershell
python run_phase5_strong.py --resume-latest
```

## Results

Phase 5 results are isolated from Phase 4:

```text
results/strong_tier/<session_id>/
```

Generate plots:

```powershell
python plot_phase5_results.py --session latest
```

Replay plans visually:

```powershell
python replay_phase5_results.py --session latest
```

Verify all replayable records:

```powershell
python verify_phase5_replays.py --session latest
```
