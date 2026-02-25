"""CueMesh Client minimal playback overlay."""
from __future__ import annotations
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class PlaybackOverlay(QWidget):
    """
    Transparent/semi-transparent overlay shown over playback,
    displays client name, state, and drift.
    Toggle visibility with a hotkey.
    """

    def __init__(self, client_id: str, client_name: str = "", parent=None):
        super().__init__(parent)
        self.client_id = client_id
        self.client_name = client_name or client_id[:12]
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: rgba(0,0,0,180);")
        self._setup_ui()
        self._visible = False
        self.hide()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        font = QFont("Monospace", 16)

        self.lbl_name = QLabel(f"CLIENT: {self.client_name}")
        self.lbl_name.setFont(font)
        self.lbl_name.setStyleSheet("color: white;")
        layout.addWidget(self.lbl_name)

        self.lbl_id = QLabel(f"ID: {self.client_id[:16]}")
        self.lbl_id.setStyleSheet("color: #aaa; font-size: 12px;")
        layout.addWidget(self.lbl_id)

        self.lbl_state = QLabel("State: idle")
        self.lbl_state.setFont(font)
        self.lbl_state.setStyleSheet("color: #4CAF50;")
        layout.addWidget(self.lbl_state)

        self.lbl_drift = QLabel("Drift: 0ms")
        self.lbl_drift.setFont(font)
        self.lbl_drift.setStyleSheet("color: #FF9800;")
        layout.addWidget(self.lbl_drift)

    def update_status(self, state: str, drift_ms: float = 0.0) -> None:
        self.lbl_state.setText(f"State: {state}")
        self.lbl_drift.setText(f"Drift: {drift_ms:+.1f}ms")

    def toggle(self) -> None:
        if self._visible:
            self.hide()
            self._visible = False
        else:
            self.show()
            self._visible = True
