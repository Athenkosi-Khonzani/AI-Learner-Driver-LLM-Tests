
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from llm_test.scenario.scenario_schema import Scenario
from llm_test.scenario.world_state_builder import build_world_state
from llm_test.ui.main_window import ArenaView
from .feasibility import conservative_feasibility
from .validator import validate_manifest


class DatasetManagerWindow(QMainWindow):
    def __init__(self, project_root: Path):
        super().__init__()
        self.project_root = project_root
        self.manifest_path = (
            project_root / "dataset" / "benchmark_manifest.json"
        )
        self.manifest = json.loads(
            self.manifest_path.read_text(encoding="utf-8")
        )

        self.setWindowTitle(
            "LLM Benchmark - Phase 3 Dataset Manager"
        )
        self.resize(1600, 920)

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)

        header = QLabel(
            f"Dataset: {self.manifest['dataset_name']}  |  "
            f"Version: {self.manifest['dataset_version']}  |  "
            f"Scenarios: {len(self.manifest['scenarios'])}  |  "
            f"LOCKED: {self.manifest.get('locked', False)}"
        )
        header.setStyleSheet(
            "font-size: 16px; font-weight: 600; padding: 8px;"
        )
        root_layout.addWidget(header)

        controls = QHBoxLayout()
        self.family_filter = QComboBox()
        self.family_filter.addItem("All families")
        families = sorted(
            {e["family"] for e in self.manifest["scenarios"]}
        )
        self.family_filter.addItems(families)
        self.family_filter.currentTextChanged.connect(
            self.populate_list
        )

        validate_btn = QPushButton("Validate Full Dataset")
        validate_btn.clicked.connect(self.validate_all)

        controls.addWidget(QLabel("Family:"))
        controls.addWidget(self.family_filter)
        controls.addStretch(1)
        controls.addWidget(validate_btn)
        root_layout.addLayout(controls)

        splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(splitter, 1)

        # Left: scenario list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(
            self.on_selection_changed
        )
        left_layout.addWidget(self.list_widget)
        splitter.addWidget(left)

        # Center: arena preview
        center = QWidget()
        center_layout = QVBoxLayout(center)
        self.arena = ArenaView()
        center_layout.addWidget(self.arena, 1)

        legend = QLabel(
            "White cross = hidden target (evaluator only). "
            "Green line = conservative reference feasibility path "
            "(dataset validation only, never sent to an LLM)."
        )
        legend.setWordWrap(True)
        center_layout.addWidget(legend)
        splitter.addWidget(center)

        # Right: metadata + JSON
        right = QWidget()
        right_layout = QVBoxLayout(right)

        self.meta = QPlainTextEdit()
        self.meta.setReadOnly(True)
        self.meta.setMaximumHeight(260)

        self.instruction = QPlainTextEdit()
        self.instruction.setReadOnly(True)
        self.instruction.setMaximumHeight(110)

        self.world_state = QPlainTextEdit()
        self.world_state.setReadOnly(True)

        meta_group = QGroupBox("Dataset metadata + hidden evaluator goal")
        mg = QVBoxLayout(meta_group)
        mg.addWidget(self.meta)

        prompt_group = QGroupBox("Visible user instruction")
        pg = QVBoxLayout(prompt_group)
        pg.addWidget(self.instruction)

        world_group = QGroupBox("Visible generated world state")
        wg = QVBoxLayout(world_group)
        wg.addWidget(self.world_state)

        right_layout.addWidget(meta_group)
        right_layout.addWidget(prompt_group)
        right_layout.addWidget(world_group, 1)
        splitter.addWidget(right)

        splitter.setSizes([330, 760, 500])

        self.populate_list()

    def filtered_entries(self):
        family = self.family_filter.currentText()
        if family == "All families":
            return self.manifest["scenarios"]
        return [
            e for e in self.manifest["scenarios"]
            if e["family"] == family
        ]

    def populate_list(self):
        self.list_widget.clear()
        for entry in self.filtered_entries():
            item = QListWidgetItem(
                f"{entry['id']}  |  D{entry['difficulty']}  |  "
                f"{entry['title']}"
            )
            item.setData(Qt.UserRole, entry)
            self.list_widget.addItem(item)

        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def on_selection_changed(self, current, previous):
        if current is None:
            return

        entry = current.data(Qt.UserRole)
        scenario_path = (
            self.project_root / "dataset" / entry["file"]
        )
        scenario = Scenario.load(scenario_path)
        feasibility = conservative_feasibility(scenario)

        self.arena.redraw(scenario)
        if feasibility.feasible:
            self._draw_reference_path(
                scenario, feasibility.path
            )

        hidden_goal = scenario.hidden_goal.__dict__

        meta = {
            "id": entry["id"],
            "family": entry["family"],
            "difficulty": entry["difficulty"],
            "title": entry["title"],
            "planning_skill": entry["planning_skill"],
            "obstacle_count": entry["obstacle_count"],
            "sha256": entry["sha256"],
            "hidden_goal_NOT_SENT_TO_LLM": hidden_goal,
            "conservative_feasibility": {
                "feasible": feasibility.feasible,
                "reason": feasibility.reason,
                "reference_path_length_mm": (
                    round(feasibility.path_length_mm, 1)
                    if feasibility.path_length_mm is not None
                    else None
                ),
                "clearance_radius_mm": round(
                    feasibility.clearance_radius_mm, 2
                ),
            },
        }

        self.meta.setPlainText(json.dumps(meta, indent=2))
        self.instruction.setPlainText(
            scenario.user_instruction
        )
        self.world_state.setPlainText(
            json.dumps(build_world_state(scenario), indent=2)
        )

    def _draw_reference_path(self, scenario, path):
        if len(path) < 2:
            return

        pen = QPen(QColor("#65d46e"), 2)
        pen.setStyle(Qt.DashLine)

        s = self.arena.scale_px_per_mm
        arena_h = scenario.arena_height_mm

        for (x1, y1), (x2, y2) in zip(path, path[1:]):
            self.arena.scene.addLine(
                x1 * s,
                (arena_h - y1) * s,
                x2 * s,
                (arena_h - y2) * s,
                pen,
            )

    def validate_all(self):
        report = validate_manifest(self.project_root)
        out_path = (
            self.project_root
            / "dataset"
            / "validation"
            / "dataset_validation_report.json"
        )
        out_path.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )

        if report["all_valid"]:
            QMessageBox.information(
                self,
                "Dataset valid",
                (
                    f"All {report['scenario_count']} scenarios passed.\n\n"
                    f"Report written to:\n{out_path}"
                ),
            )
        else:
            QMessageBox.warning(
                self,
                "Dataset validation failed",
                (
                    "One or more dataset checks failed.\n\n"
                    f"Report written to:\n{out_path}"
                ),
            )


def run(project_root: Path):
    app = QApplication.instance() or QApplication([])
    window = DatasetManagerWindow(project_root)
    window.show()
    app.exec()
