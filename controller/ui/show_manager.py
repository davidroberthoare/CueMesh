"""CueMesh Show Manager panel."""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QListWidget, QListWidgetItem, QFileDialog,
    QMessageBox, QGroupBox, QSizePolicy,
)

from controller.app_state import AppState

logger = logging.getLogger("cuemesh.controller.ui.show_manager")


class ShowManagerWidget(QWidget):
    show_loaded = Signal()

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title = QLabel("CueMesh Controller")
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #2196F3;")
        layout.addWidget(title)

        subtitle = QLabel("Open-source LAN-synchronized video/image playback for small theatres")
        subtitle.setStyleSheet("font-size: 14px; color: #888;")
        layout.addWidget(subtitle)

        # Buttons row
        btn_row = QHBoxLayout()
        self.btn_new = QPushButton("New Show")
        self.btn_open = QPushButton("Open Show...")
        self.btn_save = QPushButton("Save Show")
        self.btn_save_as = QPushButton("Save As...")
        for btn in [self.btn_new, self.btn_open, self.btn_save, self.btn_save_as]:
            btn.setMinimumHeight(48)
            btn.setStyleSheet("font-size: 14px;")
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        self.btn_new.clicked.connect(self.new_show)
        self.btn_open.clicked.connect(self.open_show)
        self.btn_save.clicked.connect(self.save_show)
        self.btn_save_as.clicked.connect(self.save_show_as)

        # Recent shows
        recent_group = QGroupBox("Recent Shows")
        recent_layout = QVBoxLayout(recent_group)
        self.recent_list = QListWidget()
        self.recent_list.setMaximumHeight(200)
        self.recent_list.itemDoubleClicked.connect(self._open_recent)
        recent_layout.addWidget(self.recent_list)
        layout.addWidget(recent_group)

        # Show info
        self.info_label = QLabel("No show loaded.")
        self.info_label.setStyleSheet("color: #aaa; font-size: 13px;")
        layout.addWidget(self.info_label)

        layout.addStretch()

    def refresh_recent(self) -> None:
        self.recent_list.clear()
        for path in self.state.recent_shows:
            self.recent_list.addItem(path)

    def _open_recent(self, item: QListWidgetItem) -> None:
        p = Path(item.text())
        if p.exists():
            self._load_show(p)
        else:
            QMessageBox.warning(self, "Not Found", f"File not found:\n{p}")

    def new_show(self) -> None:
        self.state.new_show()
        self.info_label.setText("New show created.")
        self.show_loaded.emit()

    def open_show(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Show", "", "CueMesh Shows (*.cuemesh.toml);;All Files (*)"
        )
        if path:
            self._load_show(Path(path))

    def _load_show(self, path: Path) -> None:
        try:
            self.state.load_show(path)
            self.info_label.setText(f"Loaded: {path}\nTitle: {self.state.show.title}  |  Cues: {len(self.state.show.cues)}")
            self.refresh_recent()
            self.show_loaded.emit()
        except Exception as e:
            logger.exception("Failed to load show")
            QMessageBox.critical(self, "Error", f"Failed to load show:\n{e}")

    def save_show(self) -> None:
        if self.state.show is None:
            QMessageBox.information(self, "No Show", "No show is currently loaded.")
            return
        if self.state.show_path:
            try:
                self.state.save_show()
                self.info_label.setText(f"Saved: {self.state.show_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")
        else:
            self.save_show_as()

    def save_show_as(self) -> None:
        if self.state.show is None:
            QMessageBox.information(self, "No Show", "No show is currently loaded.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Show As", "", "CueMesh Shows (*.cuemesh.toml)"
        )
        if path:
            if not path.endswith(".cuemesh.toml"):
                path += ".cuemesh.toml"
            try:
                self.state.save_show(Path(path))
                self.info_label.setText(f"Saved: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")
