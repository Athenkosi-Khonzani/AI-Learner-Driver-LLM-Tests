from __future__ import annotations

import csv
import json
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPen, QPainterPath
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QGroupBox,
    QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
    QPlainTextEdit, QSplitter, QVBoxLayout, QWidget,
)

from llm_test.analysis.core import load_records, provider_label
from llm_test.analysis.replay_utils import load_replay_bundle
from llm_test.ui.main_window import ArenaView


class ReplayArenaView(ArenaView):
    def redraw_replay(self, scenario, current_state, trail_states, show_trail=True):
        self.redraw(scenario, sim_state=current_state)
        if not show_trail or len(trail_states) < 2:
            return
        path = QPainterPath()
        s = self.scale_px_per_mm
        arena_h = scenario.arena_height_mm
        first = trail_states[0]
        path.moveTo(first.x_mm * s, (arena_h - first.y_mm) * s)
        for state in trail_states[1:]:
            path.lineTo(state.x_mm * s, (arena_h - state.y_mm) * s)
        item = self.scene.addPath(path, QPen(QColor("#ffffff"), 2))
        item.setZValue(10)


class ReplayWindow(QMainWindow):
    def __init__(self, project_root: Path, session_dir: Path):
        super().__init__()
        self.project_root = project_root
        self.session_dir = session_dir
        self.setWindowTitle(f"Phase 4 Result Replay - {session_dir.name}")
        self.resize(1550, 920)

        self.records = load_records(session_dir)
        if not self.records:
            raise RuntimeError("No completed trial records exist in this session.")

        self.bundle = None
        self.states = []
        self.frame_index = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._advance_animation)

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)

        filters = QHBoxLayout()
        self.provider_combo = QComboBox()
        for provider in sorted({r["provider_key"] for r in self.records}):
            self.provider_combo.addItem(provider_label(provider), provider)
        self.scenario_combo = QComboBox()
        self.repetition_combo = QComboBox()
        self.provider_combo.currentIndexChanged.connect(self._refresh_scenarios)
        self.scenario_combo.currentIndexChanged.connect(self._refresh_repetitions)
        self.repetition_combo.currentIndexChanged.connect(self._load_selected)
        filters.addWidget(QLabel("Model")); filters.addWidget(self.provider_combo, 1)
        filters.addWidget(QLabel("Scenario")); filters.addWidget(self.scenario_combo, 1)
        filters.addWidget(QLabel("Repetition")); filters.addWidget(self.repetition_combo)
        root_layout.addLayout(filters)

        splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(splitter, 1)

        arena_panel = QWidget(); arena_layout = QVBoxLayout(arena_panel)
        self.arena = ReplayArenaView(); arena_layout.addWidget(self.arena, 1)
        self.pose_label = QLabel(); self.pose_label.setStyleSheet("font-family: monospace;")
        arena_layout.addWidget(self.pose_label)

        controls = QHBoxLayout()
        self.restart_btn = QPushButton("Restart")
        self.play_btn = QPushButton("Play")
        self.step_back_btn = QPushButton("◀ Step")
        self.step_btn = QPushButton("Step ▶")
        self.restart_btn.clicked.connect(self.restart)
        self.play_btn.clicked.connect(self.toggle_play)
        self.step_back_btn.clicked.connect(lambda: self.step(-1))
        self.step_btn.clicked.connect(lambda: self.step(1))

        self.speed_combo = QComboBox()
        for text, value in (("0.5×",0.5),("1×",1.0),("2×",2.0),("4×",4.0),("8×",8.0)):
            self.speed_combo.addItem(text, value)
        self.speed_combo.setCurrentText("2×")

        self.trail_check = QCheckBox("Show trajectory"); self.trail_check.setChecked(True)
        self.trail_check.stateChanged.connect(self._redraw_current)

        controls.addWidget(self.restart_btn); controls.addWidget(self.play_btn)
        controls.addWidget(self.step_back_btn); controls.addWidget(self.step_btn)
        controls.addWidget(QLabel("Speed")); controls.addWidget(self.speed_combo)
        controls.addWidget(self.trail_check); controls.addStretch(1)

        export_png_btn = QPushButton("Export snapshot PNG")
        export_png_btn.clicked.connect(self.export_snapshot)
        export_csv_btn = QPushButton("Export trajectory CSV")
        export_csv_btn.clicked.connect(self.export_trajectory)
        controls.addWidget(export_png_btn); controls.addWidget(export_csv_btn)
        arena_layout.addLayout(controls)

        note = QLabel("White cross = hidden evaluator target (not sent to the LLM). White trail = replayed rover-centre trajectory.")
        note.setWordWrap(True); arena_layout.addWidget(note)
        splitter.addWidget(arena_panel)

        details = QWidget(); details_layout = QVBoxLayout(details)
        self.verification_label = QLabel(); self.verification_label.setWordWrap(True)
        details_layout.addWidget(self.verification_label)

        metrics_group = QGroupBox("Stored result + independent replay verification")
        metrics_layout = QVBoxLayout(metrics_group)
        self.metrics_text = QPlainTextEdit(); self.metrics_text.setReadOnly(True); self.metrics_text.setMaximumHeight(300)
        metrics_layout.addWidget(self.metrics_text); details_layout.addWidget(metrics_group)

        commands_group = QGroupBox("LLM plan / compiled commands")
        commands_layout = QVBoxLayout(commands_group)
        self.commands_text = QPlainTextEdit(); self.commands_text.setReadOnly(True)
        commands_layout.addWidget(self.commands_text); details_layout.addWidget(commands_group, 1)

        instruction_group = QGroupBox("Instruction sent to the LLM")
        instruction_layout = QVBoxLayout(instruction_group)
        self.instruction_text = QPlainTextEdit(); self.instruction_text.setReadOnly(True); self.instruction_text.setMaximumHeight(130)
        instruction_layout.addWidget(self.instruction_text); details_layout.addWidget(instruction_group)
        splitter.addWidget(details); splitter.setSizes([900, 600])

        self._refresh_scenarios()

    def _current_provider(self): return self.provider_combo.currentData()
    def _current_scenario(self): return self.scenario_combo.currentData()
    def _current_repetition(self): return self.repetition_combo.currentData()

    def _filtered_records(self, provider=None, scenario=None):
        rows = self.records
        if provider is not None:
            rows = [r for r in rows if r["provider_key"] == provider]
        if scenario is not None:
            rows = [r for r in rows if r["scenario_name"] == scenario]
        return rows

    def _refresh_scenarios(self):
        provider = self._current_provider()
        scenarios = sorted({r["scenario_name"] for r in self._filtered_records(provider=provider)})
        self.scenario_combo.blockSignals(True); self.scenario_combo.clear()
        for scenario in scenarios:
            self.scenario_combo.addItem(scenario, scenario)
        self.scenario_combo.blockSignals(False)
        self._refresh_repetitions()

    def _refresh_repetitions(self):
        provider = self._current_provider(); scenario = self._current_scenario()
        reps = sorted({int(r.get("repetition_index") or 0) for r in self._filtered_records(provider, scenario)})
        self.repetition_combo.blockSignals(True); self.repetition_combo.clear()
        for rep in reps:
            self.repetition_combo.addItem(str(rep), rep)
        self.repetition_combo.blockSignals(False)
        self._load_selected()

    def _record_path_for_selection(self):
        provider = self._current_provider(); scenario = self._current_scenario(); repetition = self._current_repetition()
        for row in self.records:
            if row["provider_key"] == provider and row["scenario_name"] == scenario and int(row.get("repetition_index") or 0) == repetition:
                return Path(row["_record_path"])
        return None

    def _load_selected(self):
        self.timer.stop(); self.play_btn.setText("Play")
        path = self._record_path_for_selection()
        if path is None:
            return
        try:
            self.bundle = load_replay_bundle(self.project_root, path)
        except Exception as exc:
            self.bundle = None; self.states = []
            self.metrics_text.setPlainText(f"This trial cannot be replayed:\n{exc}")
            self.verification_label.setText("Replay unavailable (no executable plan).")
            return

        self.states = self.bundle.simulation.states; self.frame_index = 0
        if self.bundle.verification_ok:
            self.verification_label.setText("✅ Independent replay matches the stored benchmark result.")
        else:
            self.verification_label.setText("⚠ Replay mismatch:\n" + "\n".join(self.bundle.verification_messages))

        r = self.bundle.record; e = self.bundle.evaluation; s = self.bundle.simulation
        metrics = {
            "provider_key": r.get("provider_key"), "model": r.get("model"),
            "scenario": r.get("scenario_name"), "repetition": r.get("repetition_index"),
            "stored_task_success": r.get("task_success"), "replayed_task_success": e.task_success,
            "stored_collision": r.get("collision"), "replayed_collision": e.collision,
            "stored_boundary_violation": r.get("boundary_violation"), "replayed_boundary_violation": e.boundary_violation,
            "stored_position_error_mm": r.get("position_error_mm"), "replayed_position_error_mm": round(e.position_error_mm, 3),
            "stored_plan_ready_latency_ms": r.get("plan_ready_latency_ms"), "estimated_cost_usd": r.get("estimated_cost_usd"),
            "final_pose_replayed": {"x_mm": round(s.final_state.x_mm,3), "y_mm": round(s.final_state.y_mm,3), "heading_deg": round(s.final_state.heading_deg,3)},
        }
        self.metrics_text.setPlainText(json.dumps(metrics, indent=2))
        self.commands_text.setPlainText(json.dumps({"parsed_plan": r.get("parsed_plan"), "wire_commands": r.get("wire_commands")}, indent=2))
        self.instruction_text.setPlainText(self.bundle.request.get("user_instruction", self.bundle.scenario.user_instruction))
        self._redraw_current()

    def _redraw_current(self):
        if not self.bundle or not self.states:
            return
        i = max(0, min(self.frame_index, len(self.states)-1)); state = self.states[i]
        trail = self.states[:i+1]
        if len(trail) > 800:
            stride = max(1, len(trail)//800); trail = trail[::stride]
            if trail[-1] is not state: trail.append(state)
        self.arena.redraw_replay(self.bundle.scenario, state, trail, self.trail_check.isChecked())
        self.pose_label.setText(f"Frame {i+1}/{len(self.states)}  |  x={state.x_mm:.1f} mm  y={state.y_mm:.1f} mm  heading={state.heading_deg:.1f}°")

    def _frame_stride(self):
        speed = float(self.speed_combo.currentData() or 1.0)
        return max(1, int(round(speed * 3)))

    def toggle_play(self):
        if not self.bundle: return
        if self.timer.isActive():
            self.timer.stop(); self.play_btn.setText("Play")
        else:
            if self.frame_index >= len(self.states)-1: self.frame_index = 0
            self.timer.start(30); self.play_btn.setText("Pause")

    def _advance_animation(self):
        if not self.states:
            self.timer.stop(); return
        self.frame_index += self._frame_stride()
        if self.frame_index >= len(self.states)-1:
            self.frame_index = len(self.states)-1; self.timer.stop(); self.play_btn.setText("Play")
        self._redraw_current()

    def restart(self):
        self.timer.stop(); self.play_btn.setText("Play"); self.frame_index = 0; self._redraw_current()

    def step(self, direction: int):
        if not self.states: return
        self.timer.stop(); self.play_btn.setText("Play")
        self.frame_index = max(0, min(len(self.states)-1, self.frame_index + direction*self._frame_stride()))
        self._redraw_current()

    def _default_export_dir(self):
        path = self.session_dir / "replay_exports"; path.mkdir(parents=True, exist_ok=True); return path

    def export_snapshot(self):
        if not self.bundle: return
        r = self.bundle.record
        default = self._default_export_dir() / f"{r['scenario_name']}__r{r.get('repetition_index')}__{r['provider_key']}__snapshot.png"
        path, _ = QFileDialog.getSaveFileName(self, "Export replay snapshot", str(default), "PNG image (*.png)")
        if path and not self.arena.grab().save(path):
            QMessageBox.warning(self, "Export failed", "The replay snapshot could not be saved.")

    def export_trajectory(self):
        if not self.bundle: return
        r = self.bundle.record
        default = self._default_export_dir() / f"{r['scenario_name']}__r{r.get('repetition_index')}__{r['provider_key']}__trajectory.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export trajectory CSV", str(default), "CSV file (*.csv)")
        if not path: return
        with Path(path).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle); writer.writerow(["frame","x_mm","y_mm","heading_deg"])
            for i, state in enumerate(self.bundle.simulation.states):
                writer.writerow([i, state.x_mm, state.y_mm, state.heading_deg])


def run(project_root: Path, session_dir: Path):
    app = QApplication.instance() or QApplication([])
    window = ReplayWindow(project_root, session_dir)
    window.show(); app.exec()
