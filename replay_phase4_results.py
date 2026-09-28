from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from llm_test.analysis.core import resolve_session_dir
from llm_test.analysis.replay_gui import run

def main():
    parser = argparse.ArgumentParser(description="Interactively replay completed Phase 4 benchmark trials.")
    parser.add_argument("--session", default="latest", help="Phase 4 session ID, or 'latest'.")
    args = parser.parse_args()
    session_dir = resolve_session_dir(ROOT, args.session)
    run(ROOT, session_dir)

if __name__ == "__main__":
    main()
