"""CueMesh Client test/alignment screen."""
from __future__ import annotations
import time
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPainter, QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class TestScreen(QWidget):
    """Fullscreen test screen showing client ID, name, drift bar, and clock tick."""

    def __init__(self, client_id: str, client_name: str = "", parent=None):
        super().__init__(parent)
        self.client_id = client_id
        self.client_name = client_name or client_id[:16]
        self._drift_ms = 0.0
        self._tick = 0
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("background: black;")
        self._setup_ui()

        self._timer = QTimer()
        self._timer.timeout.connect(self._tick_update)
        self._timer.start(500)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.lbl_name = QLabel(self.client_name)
        self.lbl_name.setAlignment(Qt.AlignCenter)
        self.lbl_name.setStyleSheet("color: white; font-size: 72px; font-weight: bold;")
        layout.addWidget(self.lbl_name)

        self.lbl_id = QLabel(f"ID: {self.client_id[:24]}")
        self.lbl_id.setAlignment(Qt.AlignCenter)
        self.lbl_id.setStyleSheet("color: #888; font-size: 24px;")
        layout.addWidget(self.lbl_id)

        self.lbl_drift = QLabel("Drift: 0ms")
        self.lbl_drift.setAlignment(Qt.AlignCenter)
        self.lbl_drift.setStyleSheet("color: #FF9800; font-size: 36px;")
        layout.addWidget(self.lbl_drift)

        self.lbl_tick = QLabel("●")
        self.lbl_tick.setAlignment(Qt.AlignCenter)
        self.lbl_tick.setStyleSheet("color: #4CAF50; font-size: 48px;")
        layout.addWidget(self.lbl_tick)

    def update_drift(self, drift_ms: float) -> None:
        self._drift_ms = drift_ms
        color = "#4CAF50" if abs(drift_ms) < 50 else "#FF9800" if abs(drift_ms) < 150 else "#F44336"
        self.lbl_drift.setStyleSheet(f"color: {color}; font-size: 36px;")
        self.lbl_drift.setText(f"Drift: {drift_ms:+.1f}ms")

    def _tick_update(self) -> None:
        self._tick = 1 - self._tick
        self.lbl_tick.setText("●" if self._tick else "○")
