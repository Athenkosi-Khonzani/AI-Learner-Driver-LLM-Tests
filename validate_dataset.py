
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from llm_test.dataset.validator import validate_manifest


if __name__ == "__main__":
    report = validate_manifest(ROOT)

    out_path = (
        ROOT
        / "dataset"
        / "validation"
        / "dataset_validation_report.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print(f"Dataset: {report['dataset_name']}")
    print(f"Version: {report['dataset_version']}")
    print(
        f"Scenarios: {report['scenario_count']} / "
        f"{report['expected_scenario_count']}"
    )
    print(f"Family counts: {report['family_counts']}")
    print(f"All valid: {report['all_valid']}")
    print()

    for item in report["scenarios"]:
        status = "PASS" if item["valid"] else "FAIL"
        path_len = item.get("reference_path_length_mm")
        print(
            f"{status:4s}  {item['id']:12s}  "
            f"family={item.get('family','?'):22s}  "
            f"D{item.get('difficulty','?')}  "
            f"ref_path={path_len}"
        )
        if item.get("problems"):
            for problem in item["problems"]:
                print(f"      - {problem}")

    print()
    print(f"Report: {out_path}")

    raise SystemExit(0 if report["all_valid"] else 1)
