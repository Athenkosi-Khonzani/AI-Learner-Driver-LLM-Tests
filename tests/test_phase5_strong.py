import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from llm_test.benchmark.phase5_batch_runner import build_session_plan

def cfgs():
    b=json.loads((ROOT/"config"/"strong_tier_benchmark_config.json").read_text())
    p=json.loads((ROOT/"config"/"phase5_strong_config.json").read_text())
    return b,p

def test_phase5_has_180_jobs_and_60_per_model():
    b,p=cfgs(); plan=build_session_plan(ROOT,b,p,seed=4022,session_id="test")
    assert len(plan["jobs"])==180
    assert Counter(j["provider_key"] for j in plan["jobs"])=={
        "openai_strong":60,"anthropic_strong":60,"gemini_strong":60}

def test_phase5_two_repetitions_per_scenario_provider():
    b,p=cfgs(); plan=build_session_plan(ROOT,b,p,seed=99,session_id="test")
    grouped=defaultdict(set)
    for j in plan["jobs"]: grouped[(j["scenario_id"],j["provider_key"])].add(j["repetition_index"])
    assert len(grouped)==90
    assert all(v=={1,2} for v in grouped.values())

def test_phase5_same_nonce_shared_within_scenario_repetition():
    b,p=cfgs(); plan=build_session_plan(ROOT,b,p,seed=1234,session_id="test")
    grouped=defaultdict(list)
    for j in plan["jobs"]: grouped[(j["scenario_id"],j["repetition_index"])].append(j)
    assert len(grouped)==60
    assert all(len(v)==3 and len({j["benchmark_nonce"] for j in v})==1 for v in grouped.values())

def test_strong_model_settings_are_medium_and_output_headroom_increased():
    b,_=cfgs()
    assert b["max_output_tokens"]==8192
    assert b["models"]["openai_strong"]["reasoning_effort"]=="medium"
    assert b["models"]["anthropic_strong"]["effort"]=="medium"
    assert b["models"]["gemini_strong"]["thinking_level"]=="medium"
