"""CueMesh Show Editor panel — cue list editing."""
from __future__ import annotations
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QGroupBox, QFormLayout,
    QLineEdit, QComboBox, QSpinBox, QCheckBox, QTextEdit,
    QSplitter, QMessageBox, QSizePolicy,
)

from controller.app_state import AppState
from shared.show import Cue

logger = logging.getLogger("cuemesh.controller.ui.show_editor")


class ShowEditorWidget(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._current_cue: Optional[Cue] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)

        # Splitter: cue list | cue detail
        splitter = QSplitter(Qt.Horizontal)

        # Left: cue list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Cue List"))

        self.cue_list = QListWidget()
        self.cue_list.currentRowChanged.connect(self._on_cue_selected)
        left_layout.addWidget(self.cue_list)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Add")
        self.btn_dup = QPushButton("Duplicate")
        self.btn_del = QPushButton("Delete")
        self.btn_up = QPushButton("▲")
        self.btn_down = QPushButton("▼")
        for btn in [self.btn_add, self.btn_dup, self.btn_del, self.btn_up, self.btn_down]:
            btn_row.addWidget(btn)
        left_layout.addLayout(btn_row)

        self.btn_add.clicked.connect(self._add_cue)
        self.btn_dup.clicked.connect(self._dup_cue)
        self.btn_del.clicked.connect(self._del_cue)
        self.btn_up.clicked.connect(self._move_up)
        self.btn_down.clicked.connect(self._move_down)

        splitter.addWidget(left)

        # Right: cue detail
        right = QGroupBox("Cue Detail")
        right_layout = QFormLayout(right)

        self.fld_id = QLineEdit()
        self.fld_name = QLineEdit()
        self.fld_type = QComboBox()
        self.fld_type.addItems(["video", "image"])
        self.fld_file = QLineEdit()
        self.fld_start_ms = QSpinBox()
        self.fld_start_ms.setRange(0, 86400000)
        self.fld_end_ms = QLineEdit()
        self.fld_end_ms.setPlaceholderText("(optional)")
        self.fld_volume = QSpinBox()
        self.fld_volume.setRange(0, 100)
        self.fld_volume.setValue(100)
        self.fld_loop = QCheckBox()
        self.fld_fade_in = QSpinBox()
        self.fld_fade_in.setRange(0, 60000)
        self.fld_fade_out = QSpinBox()
        self.fld_fade_out.setRange(0, 60000)
        self.fld_auto_follow = QLineEdit()
        self.fld_auto_follow.setPlaceholderText("(optional ms)")
        self.fld_notes = QTextEdit()
        self.fld_notes.setMaximumHeight(80)

        right_layout.addRow("ID:", self.fld_id)
        right_layout.addRow("Name:", self.fld_name)
        right_layout.addRow("Type:", self.fld_type)
        right_layout.addRow("File:", self.fld_file)
        right_layout.addRow("Start (ms):", self.fld_start_ms)
        right_layout.addRow("End (ms):", self.fld_end_ms)
        right_layout.addRow("Volume:", self.fld_volume)
        right_layout.addRow("Loop:", self.fld_loop)
        right_layout.addRow("Fade In (ms):", self.fld_fade_in)
        right_layout.addRow("Fade Out (ms):", self.fld_fade_out)
        right_layout.addRow("Auto-follow (ms):", self.fld_auto_follow)
        right_layout.addRow("Notes:", self.fld_notes)

        self.btn_apply = QPushButton("Apply Changes")
        self.btn_apply.clicked.connect(self._apply_cue)
        right_layout.addRow(self.btn_apply)

        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet("color: red;")
        right_layout.addRow(self.validation_label)

        splitter.addWidget(right)
        splitter.setSizes([350, 650])

        layout.addWidget(splitter)

    def refresh(self) -> None:
        self.cue_list.clear()
        self._current_cue = None
        if self.state.show:
            for cue in self.state.show.cues:
                self.cue_list.addItem(f"[{cue.id}] {cue.name} ({cue.type})")

    def _on_cue_selected(self, row: int) -> None:
        if self.state.show is None or row < 0 or row >= len(self.state.show.cues):
            self._current_cue = None
            return
        self._current_cue = self.state.show.cues[row]
        c = self._current_cue
        self.fld_id.setText(c.id)
        self.fld_name.setText(c.name)
        self.fld_type.setCurrentText(c.type)
        self.fld_file.setText(c.file)
        self.fld_start_ms.setValue(c.start_time_ms)
        self.fld_end_ms.setText(str(c.end_time_ms) if c.end_time_ms is not None else "")
        self.fld_volume.setValue(c.volume)
        self.fld_loop.setChecked(c.loop)
        self.fld_fade_in.setValue(c.fade_in_ms)
        self.fld_fade_out.setValue(c.fade_out_ms)
        self.fld_auto_follow.setText(str(c.auto_follow_ms) if c.auto_follow_ms is not None else "")
        self.fld_notes.setPlainText(c.notes)
        self.validation_label.setText("")

    def _apply_cue(self) -> None:
        if self._current_cue is None:
            return
        c = self._current_cue
        c.id = self.fld_id.text().strip()
        c.name = self.fld_name.text().strip()
        c.type = self.fld_type.currentText()
        c.file = self.fld_file.text().strip()
        c.start_time_ms = self.fld_start_ms.value()
        end_text = self.fld_end_ms.text().strip()
        c.end_time_ms = int(end_text) if end_text.isdigit() else None
        c.volume = self.fld_volume.value()
        c.loop = self.fld_loop.isChecked()
        c.fade_in_ms = self.fld_fade_in.value()
        c.fade_out_ms = self.fld_fade_out.value()
        af_text = self.fld_auto_follow.text().strip()
        c.auto_follow_ms = int(af_text) if af_text.isdigit() else None
        c.notes = self.fld_notes.toPlainText()

        errors = c.validate()
        if errors:
            self.validation_label.setText("\n".join(errors))
        else:
            self.validation_label.setText("")
            self.refresh()

    def _add_cue(self) -> None:
        if self.state.show is None:
            return
        import uuid
        cue = Cue(id=f"cue-{uuid.uuid4().hex[:6]}", name="New Cue", type="video", file="")
        self.state.show.cues.append(cue)
        self.refresh()
        self.cue_list.setCurrentRow(len(self.state.show.cues) - 1)

    def _dup_cue(self) -> None:
        if self.state.show is None or self._current_cue is None:
            return
        import copy, uuid
        new_cue = copy.deepcopy(self._current_cue)
        new_cue.id = f"{new_cue.id}-copy-{uuid.uuid4().hex[:4]}"
        idx = self.state.show.cues.index(self._current_cue)
        self.state.show.cues.insert(idx + 1, new_cue)
        self.refresh()
        self.cue_list.setCurrentRow(idx + 1)

    def _del_cue(self) -> None:
        if self.state.show is None or self._current_cue is None:
            return
        row = self.cue_list.currentRow()
        self.state.show.cues.pop(row)
        self._current_cue = None
        self.refresh()

    def _move_up(self) -> None:
        if self.state.show is None:
            return
        row = self.cue_list.currentRow()
        if row > 0:
            cues = self.state.show.cues
            cues[row - 1], cues[row] = cues[row], cues[row - 1]
            self.refresh()
            self.cue_list.setCurrentRow(row - 1)

    def _move_down(self) -> None:
        if self.state.show is None:
            return
        row = self.cue_list.currentRow()
        cues = self.state.show.cues
        if row < len(cues) - 1:
            cues[row], cues[row + 1] = cues[row + 1], cues[row]
            self.refresh()
            self.cue_list.setCurrentRow(row + 1)
