from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from llm_test.ui.main_window import run

if __name__ == "__main__":
    run()
