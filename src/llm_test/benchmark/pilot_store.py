from __future__ import annotations

import csv
import json
from pathlib import Path

from .benchmark_record import BenchmarkRecord


class PilotResultStore:
    """
    Phase 4 results are isolated by session so smoke-test rows and pilot rows
    are never mixed accidentally.
    """

    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.records_dir = session_dir / "records"
        self.records_dir.mkdir(parents=True, exist_ok=True)

        self.jsonl_path = session_dir / "pilot_results.jsonl"
        self.csv_path = session_dir / "pilot_results.csv"

    def record_path(self, job_id: str) -> Path:
        return self.records_dir / f"{job_id}.json"

    def is_complete(self, job_id: str) -> bool:
        return self.record_path(job_id).exists()

    def completed_job_ids(self) -> set[str]:
        return {
            path.stem
            for path in self.records_dir.glob("*.json")
        }

    def save_record(
        self,
        record: BenchmarkRecord,
        request_payload: dict,
    ) -> Path:
        if not record.job_id:
            raise ValueError(
                "Phase 4 records require a job_id."
            )

        path = self.record_path(record.job_id)

        payload = {
            "request": request_payload,
            "record": record.to_dict(),
        }

        # Atomic-ish replace: write a temporary file first.
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        tmp.replace(path)

        with self.jsonl_path.open(
            "a", encoding="utf-8"
        ) as handle:
            handle.write(
                json.dumps(
                    record.to_dict(),
                    ensure_ascii=False,
                )
                + "\n"
            )

        return path

    def append_csv(self, record: BenchmarkRecord) -> None:
        row = record.to_dict()

        for key in (
            "raw_response",
            "parsed_plan",
            "wire_commands",
        ):
            row.pop(key, None)

        fields = list(row.keys())
        exists = self.csv_path.exists()

        with self.csv_path.open(
            "a",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=fields,
            )

            if not exists:
                writer.writeheader()

            writer.writerow(row)
