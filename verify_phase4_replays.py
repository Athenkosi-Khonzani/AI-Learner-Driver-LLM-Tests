from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from llm_test.analysis.core import resolve_session_dir
from llm_test.analysis.replay_utils import load_replay_bundle

def main():
    parser = argparse.ArgumentParser(description="Re-simulate completed Phase 4 records and verify stored outcomes.")
    parser.add_argument("--session", default="latest")
    args = parser.parse_args()
    session_dir = resolve_session_dir(ROOT, args.session)
    record_paths = sorted((session_dir / "records").glob("*.json"))
    checked = skipped = 0; mismatches = []
    for path in record_paths:
        try:
            bundle = load_replay_bundle(ROOT, path)
        except Exception as exc:
            skipped += 1; print(f"SKIP {path.name}: {exc}"); continue
        checked += 1
        if not bundle.verification_ok:
            mismatches.append((path.name, bundle.verification_messages))
    print(); print(f"Replayable records checked: {checked}")
    print(f"Non-replayable records skipped: {skipped}")
    print(f"Replay mismatches: {len(mismatches)}")
    for filename, messages in mismatches:
        print(f"\n{filename}")
        for message in messages: print(f"  - {message}")
    raise SystemExit(1 if mismatches else 0)

if __name__ == "__main__":
    main()
