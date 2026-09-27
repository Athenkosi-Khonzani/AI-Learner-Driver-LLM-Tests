# LLM Test - Phase 1

Standalone benchmark simulator for the AI Learner Rover Driver research project.

Phase 1 intentionally contains **no LLM APIs** and has no dependency on the production
`ai_learner_host` application. Its purpose is to validate:

- scenario creation,
- the canonical benchmark world-state schema,
- the rover command schema,
- deterministic rover simulation,
- full-body collision/boundary checking,
- objective goal evaluation.

## Run

From this folder:

```bash
pip install -r requirements.txt
python run_simulator.py
```

## Controls

Use the GUI to:
- add or select the rover and coloured blocks,
- edit X/Y/length/breadth/heading or orientation,
- enter a natural-language user instruction,
- define a hidden evaluator goal,
- generate the world state,
- paste a command plan,
- simulate it,
- save/load scenarios.

