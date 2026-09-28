# Experiment Protocol - Draft

Phase 1 does not call any external LLM.

Before Phase 2:
1. Validate coordinate conventions.
2. Validate full-body collision behavior.
3. Validate TURN direction.
4. Validate FWD/BACK motion.
5. Validate hidden-goal scoring.
6. Save a small set of known-good scenarios.
7. Freeze simulator rules before collecting model benchmark data.


## Phase 4 pilot

The first statistical pilot uses 30 frozen scenarios × 3 repetitions × 4 model
entries = 360 sequential calls. The schedule is randomized once, saved, and resumed
without re-randomizing. No automatic retry is used.
