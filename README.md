# LLM Test

Standalone LLM-planning benchmark for the AI Learner Rover Driver research project.

This project intentionally does **not** import from or modify `ai_learner_host`.

## Phase 1

Validated deterministic simulator, full-body collisions, command protocol and hidden
goal evaluator.

## Phase 2

Adds provider adapters and a reproducible smoke benchmark for:

- OpenAI
- Anthropic Claude Haiku
- Google Gemini Flash-Lite
- Anthropic Claude Sonnet baseline

API keys are read from:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`

They are never saved into source or result files.

## Install

```powershell
pip install -r requirements.txt
```

## Simulator

```powershell
python run_simulator.py
```

## Phase 2 smoke benchmark

Run one scenario once against all four configured model entries:

```powershell
python run_benchmark_smoke.py
```

Or test one provider first:

```powershell
python run_benchmark_smoke.py --providers openai_fast
```

Then:

```powershell
python run_benchmark_smoke.py --providers anthropic_fast
python run_benchmark_smoke.py --providers gemini_fast
python run_benchmark_smoke.py --providers anthropic_baseline
```

Default mode is provider-native structured output.

The later prompt-only format stress test is available with:

```powershell
python run_benchmark_smoke.py --mode prompt_only
```

Do not collect the final benchmark dataset until the smoke test has been inspected and
the Phase 2 prompt/model configuration has been frozen.
