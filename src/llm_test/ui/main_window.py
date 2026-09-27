from __future__ import annotations

import json
import math
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QColor, QBrush, QPen, QPolygonF
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from llm_test.commands.command_schema import (
    parse_plan,
    compile_wire_commands,
    CommandValidationError,
)
from llm_test.scenario.scenario_schema import (
    Scenario,
    BlockSpec,
)
from llm_test.scenario.world_state_builder import (
    build_world_state,
)
from llm_test.simulator.rover_simulator import (
    RoverSimulator,
)
from llm_test.simulator.evaluator import evaluate
from llm_test.simulator.geometry import (
    RectPose,
    rectangle_polygon,
)


COLOUR_MAP = {
    "red": QColor("#d95f59"),
    "green": QColor("#5cb85c"),
    "yellow": QColor("#e7c547"),
    "blue": QColor("#4f8bd6"),
}


class ArenaView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(650, 650)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.scene.setBackgroundBrush(QBrush(QColor("#171a1f")))

        self.scale_px_per_mm = 0.24

    def redraw(
        self,
        scenario: Scenario,
        sim_state=None
    ) -> None:
        self.scene.clear()

        w = scenario.arena_width_mm * self.scale_px_per_mm
        h = scenario.arena_height_mm * self.scale_px_per_mm

        self.scene.setSceneRect(0, 0, w, h)

        self.scene.addRect(
            0,
            0,
            w,
            h,
            QPen(QColor("#aeb5bf"), 2),
        )

        for block in scenario.blocks:
            self._draw_rect(
                block.x_mm,
                block.y_mm,
                block.length_mm,
                block.breadth_mm,
                block.orientation_deg,
                COLOUR_MAP[block.colour],
                label=block.id,
                arena_height=scenario.arena_height_mm,
            )

        rover = scenario.rover

        rx = rover.x_mm if sim_state is None else sim_state.x_mm
        ry = rover.y_mm if sim_state is None else sim_state.y_mm
        rh = rover.heading_deg if sim_state is None else sim_state.heading_deg

        self._draw_rect(
            rx,
            ry,
            rover.length_mm,
            rover.breadth_mm,
            rh,
            QColor("#62d5ff"),
            label="ROVER",
            arena_height=scenario.arena_height_mm,
        )

        # Hidden goal shown as a cross for simulator development.
        gx = scenario.hidden_goal.target_x_mm * self.scale_px_per_mm
        gy = (
            scenario.arena_height_mm
            - scenario.hidden_goal.target_y_mm
        ) * self.scale_px_per_mm

        self.scene.addLine(
            gx - 8, gy,
            gx + 8, gy,
            QPen(QColor("#ffffff"), 2)
        )
        self.scene.addLine(
            gx, gy - 8,
            gx, gy + 8,
            QPen(QColor("#ffffff"), 2)
        )

    def _draw_rect(
        self,
        x_mm,
        y_mm,
        length_mm,
        breadth_mm,
        heading_deg,
        colour,
        label,
        arena_height,
    ):
        poly_world = rectangle_polygon(
            RectPose(
                x_mm=x_mm,
                y_mm=y_mm,
                length_mm=length_mm,
                breadth_mm=breadth_mm,
                heading_deg=heading_deg,
            )
        )

        poly = QPolygonF()

        for x, y in poly_world:
            poly.append(
                QPointF(
                    x * self.scale_px_per_mm,
                    (arena_height - y)
                    * self.scale_px_per_mm,
                )
            )

        item = QGraphicsPolygonItem(poly)
        item.setBrush(QBrush(colour))
        item.setPen(QPen(QColor("#f0f0f0"), 1.5))
        self.scene.addItem(item)

        centre_x = x_mm * self.scale_px_per_mm
        centre_y = (
            arena_height - y_mm
        ) * self.scale_px_per_mm

        text = self.scene.addText(label)
        text.setDefaultTextColor(QColor("#ffffff"))
        text.setPos(centre_x + 6, centre_y + 6)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "LLM Test - Phase 1 Scenario Lab"
        )

        self.resize(1500, 900)

        self.scenario = Scenario(
            name="phase1_test",
            blocks=[
                BlockSpec(
                    id="red_block_01",
                    colour="red",
                    x_mm=1250,
                    y_mm=1350,
                    length_mm=320,
                    breadth_mm=220,
                    orientation_deg=0,
                )
            ]
        )

        self.sim_states = []
        self.sim_index = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(
            self._animate_next
        )

        self.arena = ArenaView()

        root = QWidget()
        self.setCentralWidget(root)

        layout = QHBoxLayout(root)

        left = QVBoxLayout()
        left.addWidget(self.arena)

        instruction_group = QGroupBox(
            "User instruction"
        )
        instruction_layout = QVBoxLayout(
            instruction_group
        )
        self.instruction_edit = QPlainTextEdit(
            self.scenario.user_instruction
        )
        self.instruction_edit.setMaximumHeight(100)
        instruction_layout.addWidget(
            self.instruction_edit
        )
        left.addWidget(instruction_group)

        layout.addLayout(left, 3)

        right = QVBoxLayout()

        right.addWidget(
            self._build_scenario_controls()
        )

        right.addWidget(
            self._build_goal_controls()
        )

        world_group = QGroupBox(
            "Generated world state"
        )
        world_layout = QVBoxLayout(
            world_group
        )
        self.world_text = QPlainTextEdit()
        self.world_text.setReadOnly(True)
        world_layout.addWidget(self.world_text)

        btn_world = QPushButton(
            "Generate World State"
        )
        btn_world.clicked.connect(
            self.refresh_world_state
        )
        world_layout.addWidget(btn_world)

        right.addWidget(world_group, 1)

        plan_group = QGroupBox(
            "Command plan"
        )
        plan_layout = QVBoxLayout(
            plan_group
        )

        self.plan_text = QPlainTextEdit(
            json.dumps(
                {
                    "cmds": [
                        {
                            "op": "TURN",
                            "value": 45
                        },
                        {
                            "op": "FWD",
                            "value": 500
                        },
                        {
                            "op": "STOP",
                            "value": None
                        }
                    ]
                },
                indent=2
            )
        )

        plan_layout.addWidget(
            self.plan_text
        )

        btn_sim = QPushButton(
            "Validate + Simulate Plan"
        )
        btn_sim.clicked.connect(
            self.simulate_plan
        )
        plan_layout.addWidget(btn_sim)

        right.addWidget(plan_group, 1)

        results_group = QGroupBox(
            "Evaluation"
        )
        results_layout = QVBoxLayout(
            results_group
        )

        self.results_text = QPlainTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMaximumHeight(180)

        results_layout.addWidget(
            self.results_text
        )

        right.addWidget(results_group)

        file_row = QHBoxLayout()

        btn_save = QPushButton(
            "Save Scenario"
        )
        btn_save.clicked.connect(
            self.save_scenario
        )

        btn_load = QPushButton(
            "Load Scenario"
        )
        btn_load.clicked.connect(
            self.load_scenario
        )

        file_row.addWidget(btn_save)
        file_row.addWidget(btn_load)

        right.addLayout(file_row)

        layout.addLayout(right, 2)

        self._sync_ui_from_scenario()
        self.refresh_all()

    def _spin(
        self,
        minimum,
        maximum,
        value,
        decimals=1
    ):
        s = QDoubleSpinBox()
        s.setRange(minimum, maximum)
        s.setDecimals(decimals)
        s.setValue(value)
        s.setSingleStep(10.0)
        s.valueChanged.connect(
            self._apply_ui_to_scenario
        )
        return s

    def _build_scenario_controls(self):
        group = QGroupBox(
            "Rover + obstacle editor"
        )
        form = QFormLayout(group)

        self.rover_x = self._spin(
            0, 2500, 400
        )
        self.rover_y = self._spin(
            0, 2500, 400
        )
        self.rover_length = self._spin(
            20, 1000, 180
        )
        self.rover_breadth = self._spin(
            20, 1000, 140
        )
        self.rover_heading = self._spin(
            0, 359.9, 0
        )

        form.addRow("Rover X [mm]", self.rover_x)
        form.addRow("Rover Y [mm]", self.rover_y)
        form.addRow(
            "Rover length [mm]",
            self.rover_length
        )
        form.addRow(
            "Rover breadth [mm]",
            self.rover_breadth
        )
        form.addRow(
            "Rover heading [deg]",
            self.rover_heading
        )

        self.block_select = QComboBox()
        self.block_select.currentIndexChanged.connect(
            self._load_selected_block
        )

        form.addRow(
            "Selected block",
            self.block_select
        )

        self.block_colour = QComboBox()
        self.block_colour.addItems(
            ["red", "green", "yellow", "blue"]
        )
        self.block_colour.currentTextChanged.connect(
            self._apply_ui_to_scenario
        )

        self.block_x = self._spin(
            0, 2500, 1250
        )
        self.block_y = self._spin(
            0, 2500, 1350
        )
        self.block_length = self._spin(
            20, 1200, 300
        )
        self.block_breadth = self._spin(
            20, 1200, 200
        )
        self.block_orientation = self._spin(
            0, 179.9, 0
        )

        form.addRow(
            "Block colour",
            self.block_colour
        )
        form.addRow(
            "Block X [mm]",
            self.block_x
        )
        form.addRow(
            "Block Y [mm]",
            self.block_y
        )
        form.addRow(
            "Block length [mm]",
            self.block_length
        )
        form.addRow(
            "Block breadth [mm]",
            self.block_breadth
        )
        form.addRow(
            "Block orientation [deg]",
            self.block_orientation
        )

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)

        add_btn = QPushButton(
            "Add Block"
        )
        add_btn.clicked.connect(
            self.add_block
        )

        delete_btn = QPushButton(
            "Delete Block"
        )
        delete_btn.clicked.connect(
            self.delete_block
        )

        row_layout.addWidget(add_btn)
        row_layout.addWidget(delete_btn)

        form.addRow(row)

        return group

    def _build_goal_controls(self):
        group = QGroupBox(
            "Hidden evaluator goal (NOT sent to LLM)"
        )
        form = QFormLayout(group)

        self.goal_x = self._spin(
            0, 2500, 2000
        )
        self.goal_y = self._spin(
            0, 2500, 2000
        )
        self.goal_tol = self._spin(
            1, 1000, 75
        )

        self.goal_heading = self._spin(
            0, 359.9, 0
        )

        self.require_heading = QComboBox()
        self.require_heading.addItems(
            ["No", "Yes"]
        )
        self.require_heading.currentTextChanged.connect(
            self._apply_ui_to_scenario
        )

        self.heading_tol = self._spin(
            1, 180, 15
        )

        form.addRow(
            "Target X [mm]",
            self.goal_x
        )
        form.addRow(
            "Target Y [mm]",
            self.goal_y
        )
        form.addRow(
            "Position tolerance [mm]",
            self.goal_tol
        )
        form.addRow(
            "Require heading",
            self.require_heading
        )
        form.addRow(
            "Target heading [deg]",
            self.goal_heading
        )
        form.addRow(
            "Heading tolerance [deg]",
            self.heading_tol
        )

        return group

    def _sync_ui_from_scenario(self):
        r = self.scenario.rover

        for widget, value in (
            (self.rover_x, r.x_mm),
            (self.rover_y, r.y_mm),
            (self.rover_length, r.length_mm),
            (self.rover_breadth, r.breadth_mm),
            (self.rover_heading, r.heading_deg),
        ):
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)

        g = self.scenario.hidden_goal

        for widget, value in (
            (self.goal_x, g.target_x_mm),
            (self.goal_y, g.target_y_mm),
            (self.goal_tol, g.position_tolerance_mm),
            (self.goal_heading, g.target_heading_deg),
            (self.heading_tol, g.heading_tolerance_deg),
        ):
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)

        self.require_heading.blockSignals(True)
        self.require_heading.setCurrentText(
            "Yes" if g.require_heading else "No"
        )
        self.require_heading.blockSignals(False)

        self.instruction_edit.setPlainText(
            self.scenario.user_instruction
        )

        self.block_select.blockSignals(True)
        self.block_select.clear()

        for block in self.scenario.blocks:
            self.block_select.addItem(
                block.id
            )

        self.block_select.blockSignals(False)

        if self.scenario.blocks:
            self.block_select.setCurrentIndex(0)
            self._load_selected_block()

    def _selected_block(self):
        idx = self.block_select.currentIndex()

        if 0 <= idx < len(self.scenario.blocks):
            return self.scenario.blocks[idx]

        return None

    def _load_selected_block(self):
        block = self._selected_block()

        if block is None:
            return

        widgets = [
            (
                self.block_colour,
                block.colour
            ),
            (
                self.block_x,
                block.x_mm
            ),
            (
                self.block_y,
                block.y_mm
            ),
            (
                self.block_length,
                block.length_mm
            ),
            (
                self.block_breadth,
                block.breadth_mm
            ),
            (
                self.block_orientation,
                block.orientation_deg
            ),
        ]

        for widget, value in widgets:
            widget.blockSignals(True)

            if isinstance(widget, QComboBox):
                widget.setCurrentText(
                    str(value)
                )
            else:
                widget.setValue(value)

            widget.blockSignals(False)

    def _apply_ui_to_scenario(self, *args):
        r = self.scenario.rover

        r.x_mm = self.rover_x.value()
        r.y_mm = self.rover_y.value()
        r.length_mm = self.rover_length.value()
        r.breadth_mm = self.rover_breadth.value()
        r.heading_deg = self.rover_heading.value()

        g = self.scenario.hidden_goal

        g.target_x_mm = self.goal_x.value()
        g.target_y_mm = self.goal_y.value()
        g.position_tolerance_mm = self.goal_tol.value()

        g.require_heading = (
            self.require_heading.currentText()
            == "Yes"
        )

        g.target_heading_deg = (
            self.goal_heading.value()
        )

        g.heading_tolerance_deg = (
            self.heading_tol.value()
        )

        self.scenario.user_instruction = (
            self.instruction_edit.toPlainText()
        )

        block = self._selected_block()

        if block is not None:
            block.colour = (
                self.block_colour.currentText()
            )

            block.x_mm = self.block_x.value()
            block.y_mm = self.block_y.value()
            block.length_mm = (
                self.block_length.value()
            )
            block.breadth_mm = (
                self.block_breadth.value()
            )
            block.orientation_deg = (
                self.block_orientation.value()
            )

        self.refresh_all()

    def refresh_all(self):
        self.arena.redraw(self.scenario)
        self.refresh_world_state()

    def refresh_world_state(self):
        try:
            state = build_world_state(
                self.scenario
            )

            self.world_text.setPlainText(
                json.dumps(
                    state,
                    indent=2
                )
            )
        except Exception as exc:
            self.world_text.setPlainText(
                f"World-state error: {exc}"
            )

    def add_block(self):
        index = len(self.scenario.blocks) + 1

        colour = "blue"

        self.scenario.blocks.append(
            BlockSpec(
                id=f"{colour}_block_{index:02d}",
                colour=colour,
                x_mm=1500,
                y_mm=1500,
            )
        )

        self._sync_ui_from_scenario()
        self.block_select.setCurrentIndex(
            len(self.scenario.blocks) - 1
        )
        self.refresh_all()

    def delete_block(self):
        idx = self.block_select.currentIndex()

        if 0 <= idx < len(self.scenario.blocks):
            self.scenario.blocks.pop(idx)
            self._sync_ui_from_scenario()
            self.refresh_all()

    def simulate_plan(self):
        self._apply_ui_to_scenario()

        try:
            raw = json.loads(
                self.plan_text.toPlainText()
            )

            commands = parse_plan(raw)

        except (
            json.JSONDecodeError,
            CommandValidationError,
        ) as exc:

            QMessageBox.warning(
                self,
                "Invalid plan",
                str(exc)
            )
            return

        simulator = RoverSimulator(
            self.scenario
        )

        result = simulator.simulate(
            commands
        )

        score = evaluate(
            self.scenario,
            result
        )

        wire = compile_wire_commands(
            commands
        )

        report = [
            f"TASK SUCCESS        {score.task_success}",
            f"SAFE                {score.safe}",
            f"STOP REACHED        {score.stop_reached}",
            f"COLLISION           {score.collision}",
            f"BOUNDARY VIOLATION  {score.boundary_violation}",
            "",
            (
                "FINAL POSE          "
                f"x={result.final_state.x_mm:.1f} mm  "
                f"y={result.final_state.y_mm:.1f} mm  "
                f"heading={result.final_state.heading_deg:.1f} deg"
            ),
            (
                "POSITION ERROR      "
                f"{score.position_error_mm:.1f} mm"
            ),
            (
                "HEADING ERROR       "
                + (
                    f"{score.heading_error_deg:.1f} deg"
                    if score.heading_error_deg is not None
                    else "not required"
                )
            ),
            "",
            (
                "TRAVEL DISTANCE     "
                f"{score.travel_distance_mm:.1f} mm"
            ),
            (
                "TOTAL ROTATION      "
                f"{score.total_rotation_deg:.1f} deg"
            ),
            (
                "COMMANDS EXECUTED   "
                f"{score.commands_executed}"
            ),
            "",
            "WIRE COMMANDS:",
            json.dumps(wire, indent=2),
        ]

        self.results_text.setPlainText(
            "\n".join(report)
        )

        self.sim_states = result.states
        self.sim_index = 0

        self.timer.start(15)

    def _animate_next(self):
        if self.sim_index >= len(self.sim_states):
            self.timer.stop()
            return

        state = self.sim_states[
            self.sim_index
        ]

        self.arena.redraw(
            self.scenario,
            state
        )

        # Compress long traces while keeping animation visible.
        step = max(
            1,
            len(self.sim_states) // 350
        )

        self.sim_index += step

    def save_scenario(self):
        self._apply_ui_to_scenario()

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Scenario",
            "scenario.json",
            "JSON files (*.json)"
        )

        if path:
            self.scenario.save(path)

    def load_scenario(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Scenario",
            "",
            "JSON files (*.json)"
        )

        if not path:
            return

        try:
            self.scenario = Scenario.load(path)
            self._sync_ui_from_scenario()
            self.refresh_all()

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Load failed",
                str(exc)
            )


def run():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
