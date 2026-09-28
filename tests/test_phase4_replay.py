import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from llm_test.analysis.replay_utils import load_replay_bundle

def test_replay_recomputes_stored_success(tmp_path):
    payload = {
        "request": {"user_instruction": "Move forward 500 mm and stop."},
        "record": {
            "scenario_name": "BASIC_01",
            "parsed_plan": {"cmds": [{"op":"FWD","value":500},{"op":"STOP","value":None}]},
            "task_success": True,
            "collision": False,
            "boundary_violation": False,
            "stop_reached": True,
            "final_x_mm": 500.0,
            "final_y_mm": 1000.0,
            "final_heading_deg": 0.0,
        },
    }
    path = tmp_path / "record.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    bundle = load_replay_bundle(ROOT, path)
    assert bundle.verification_ok is True
    assert bundle.evaluation.task_success is True
