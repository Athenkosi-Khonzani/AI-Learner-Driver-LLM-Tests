\
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_test.providers.helpers import extract_json_object


def test_extract_json_from_code_fence():
    result = extract_json_object(
        '```json\n{"cmds": [{"op":"STOP","value":null}]}\n```'
    )

    assert result["cmds"][0]["op"] == "STOP"
