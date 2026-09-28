from __future__ import annotations

import csv
import json
from pathlib import Path

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
            f"{record.run_index:03d}_"
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

        for key in (
            "raw_response",
            "parsed_plan",
            "wire_commands",
        ):
            row.pop(key, None)

        # If an older CSV exists with the Phase 2 header, migrate it to the
        # current superset header rather than failing when Phase 4 fields appear.
        if path.exists():
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                existing_rows = list(reader)
                old_fields = reader.fieldnames or []

            new_fields = list(row.keys())
            merged_fields = old_fields + [
                f for f in new_fields if f not in old_fields
            ]

            if merged_fields != old_fields:
                with path.open(
                    "w", encoding="utf-8", newline=""
                ) as handle:
                    writer = csv.DictWriter(
                        handle, fieldnames=merged_fields
                    )
                    writer.writeheader()
                    for existing in existing_rows:
                        writer.writerow(existing)
        else:
            merged_fields = list(row.keys())

        with path.open(
            "a",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=merged_fields,
                extrasaction="ignore",
            )

            if path.stat().st_size == 0:
                writer.writeheader()

            writer.writerow(row)
