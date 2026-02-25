"""CueMesh Diagnostics panel — logs, test screen, support bundle."""
from __future__ import annotations
import asyncio
import logging
import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QFileDialog, QGroupBox, QCheckBox,
)

from controller.app_state import AppState

logger = logging.getLogger("cuemesh.controller.ui.diagnostics")


class DiagnosticsWidget(QWidget):
    def __init__(self, state: AppState, server, log_aggregator, loop: asyncio.AbstractEventLoop, parent=None):
        super().__init__(parent)
        self.state = state
        self.server = server
        self.log_aggregator = log_aggregator
        self.loop = loop
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Diagnostics & Logging")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # Test screen toggle
        test_group = QGroupBox("Alignment / Test Screen")
        test_layout = QHBoxLayout(test_group)
        self.btn_testscreen = QPushButton("Show Test Screen on All Clients")
        self.btn_testscreen.setCheckable(True)
        self.btn_testscreen.clicked.connect(self._on_testscreen)
        test_layout.addWidget(self.btn_testscreen)
        test_layout.addStretch()
        layout.addWidget(test_group)

        # Log viewer
        log_group = QGroupBox("Log Viewer")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(400)
        self.log_view.setStyleSheet("font-family: monospace; font-size: 11px;")
        log_layout.addWidget(self.log_view)

        log_btns = QHBoxLayout()
        self.btn_refresh_logs = QPushButton("Refresh Logs")
        self.btn_refresh_logs.clicked.connect(self._refresh_logs)
        self.btn_clear_logs = QPushButton("Clear View")
        self.btn_clear_logs.clicked.connect(self.log_view.clear)
        log_btns.addWidget(self.btn_refresh_logs)
        log_btns.addWidget(self.btn_clear_logs)
        log_btns.addStretch()
        log_layout.addLayout(log_btns)
        layout.addWidget(log_group)

        # Export bundle
        export_group = QGroupBox("Support Bundle")
        export_layout = QHBoxLayout(export_group)
        self.btn_export = QPushButton("Export Support Bundle (ZIP)")
        self.btn_export.setMinimumHeight(40)
        self.btn_export.clicked.connect(self._export_bundle)
        export_layout.addWidget(self.btn_export)
        export_layout.addStretch()
        layout.addWidget(export_group)

        layout.addStretch()

    def _on_testscreen(self, checked: bool) -> None:
        asyncio.run_coroutine_threadsafe(
            self.server.send_testscreen(checked), self.loop
        )
        if checked:
            self.btn_testscreen.setText("Hide Test Screen")
        else:
            self.btn_testscreen.setText("Show Test Screen on All Clients")

    def _refresh_logs(self) -> None:
        log_dir = Path("logs")
        lines = []
        if log_dir.exists():
            for f in sorted(log_dir.glob("*.log"))[-3:]:
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                    lines.append(f"=== {f.name} ===\n")
                    lines.append(content[-10000:])
                except Exception as e:
                    lines.append(f"Error reading {f.name}: {e}\n")
        self.log_view.setPlainText("".join(lines))
        self.log_view.verticalScrollBar().setValue(
            self.log_view.verticalScrollBar().maximum()
        )

    def _export_bundle(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Support Bundle", "cuemesh_support_bundle.zip", "ZIP Files (*.zip)"
        )
        if not path:
            return
        try:
            bundle = self.log_aggregator.export_bundle(self.state.show_path)
            with open(path, "wb") as f:
                f.write(bundle)
            logger.info("Exported support bundle: %s", path)
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Exported", f"Support bundle saved to:\n{path}")
        except Exception as e:
            logger.exception("Failed to export bundle")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Failed to export bundle:\n{e}")
