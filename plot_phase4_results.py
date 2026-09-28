from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from llm_test.analysis.core import resolve_session_dir
from llm_test.analysis.plotter import generate_all_plots


def main():
    parser = argparse.ArgumentParser(description="Generate Phase 4 comparison plots and analysis CSVs.")
    parser.add_argument("--session", default="latest", help="Phase 4 session ID, or 'latest'.")
    args = parser.parse_args()
    session_dir = resolve_session_dir(ROOT, args.session)
    result = generate_all_plots(session_dir)
    print(f"Analysed {result['records_analyzed']} completed trials.")
    print(f"Generated {len(result['plots_generated'])} plots.")
    print(f"Output: {session_dir / 'analysis'}")
    for plot in result["plots_generated"]:
        print(f"  {plot}")


if __name__ == "__main__":
    main()
