from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/"src"))
from llm_test.analysis.core import resolve_session_dir
from llm_test.analysis.replay_utils import load_replay_bundle

def main():
    p=argparse.ArgumentParser(description="Re-simulate Phase 5 records and verify stored outcomes.")
    p.add_argument("--session",default="latest")
    a=p.parse_args()
    session=resolve_session_dir(ROOT,a.session,group="strong_tier")
    checked=skipped=0; mismatches=[]
    for path in sorted((session/"records").glob("*.json")):
        try: b=load_replay_bundle(ROOT,path)
        except Exception as exc:
            skipped+=1; print(f"SKIP {path.name}: {exc}"); continue
        checked+=1
        if not b.verification_ok: mismatches.append((path.name,b.verification_messages))
    print(f"Replayable records checked: {checked}")
    print(f"Non-replayable records skipped: {skipped}")
    print(f"Replay mismatches: {len(mismatches)}")
    for name,msgs in mismatches:
        print(name); [print(f"  - {m}") for m in msgs]
    raise SystemExit(1 if mismatches else 0)
if __name__=="__main__": main()
