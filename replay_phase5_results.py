from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/"src"))
from llm_test.analysis.core import resolve_session_dir
from llm_test.analysis.replay_gui import run

def main():
    p=argparse.ArgumentParser(description="Replay Phase 5 strong-tier benchmark trials.")
    p.add_argument("--session",default="latest")
    a=p.parse_args()
    run(ROOT, resolve_session_dir(ROOT,a.session,group="strong_tier"))
if __name__=="__main__": main()
