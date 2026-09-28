import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_test.analysis.core import wilson_interval


def test_wilson_interval_contains_perfect_observed_rate():
    low, high = wilson_interval(60, 60)
    assert low <= 1.0 <= high
    assert high == 1.0


def test_wilson_interval_contains_zero_observed_rate():
    low, high = wilson_interval(0, 60)
    assert low <= 0.0 <= high
    assert low == 0.0
