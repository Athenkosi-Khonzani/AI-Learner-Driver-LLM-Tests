from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from llm_test.analysis.core import resolve_session_dir
from llm_test.analysis.plotter import generate_all_plots

def main():
    p=argparse.ArgumentParser(description="Generate Phase 5 strong-tier comparison plots.")
    p.add_argument("--session",default="latest")
    a=p.parse_args()
    session_dir=resolve_session_dir(ROOT,a.session,group="strong_tier")
    result=generate_all_plots(session_dir)
    print(f"Analysed {result['records_analyzed']} completed trials.")
    print(f"Generated {len(result['plots_generated'])} plots.")
    print(f"Output: {session_dir / 'analysis'}")
if __name__=="__main__": main()
