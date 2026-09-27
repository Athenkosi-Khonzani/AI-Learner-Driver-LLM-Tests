\
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .benchmark_record import BenchmarkRecord


class ResultStore:
    def __init__(self, project_root: Path, session_id: str):
        self.project_root = project_root
        self.session_id = session_id

        self.raw_dir = (
            project_root / "results" / "raw" / session_id
        )
        self.processed_dir = (
            project_root / "results" / "processed"
        )

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def save_record(
        self,
        record: BenchmarkRecord,
        request_payload: dict,
    ) -> Path:

        filename = (
            f"{record.run_index:02d}_"
            f"{record.provider_key}_"
            f"{record.scenario_name}.json"
        )

        path = self.raw_dir / filename

        payload = {
            "request": request_payload,
            "record": record.to_dict(),
        }

        path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

        self.append_jsonl(record)
        return path

    def append_jsonl(self, record: BenchmarkRecord) -> None:
        path = self.processed_dir / "benchmark_results.jsonl"

        with path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(record.to_dict(), ensure_ascii=False)
                + "\n"
            )

    def append_csv(self, record: BenchmarkRecord) -> None:
        path = self.processed_dir / "benchmark_results.csv"

        row = record.to_dict()

        # Keep large/nested fields out of the CSV.
        for key in (
            "raw_response",
            "parsed_plan",
            "wire_commands",
        ):
            row.pop(key, None)

        exists = path.exists()

        with path.open(
            "a",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=list(row.keys()),
            )

            if not exists:
                writer.writeheader()

            writer.writerow(row)
