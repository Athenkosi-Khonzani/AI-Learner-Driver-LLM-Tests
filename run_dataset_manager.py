
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from llm_test.dataset.manager_window import run

if __name__ == "__main__":
    run(ROOT)
