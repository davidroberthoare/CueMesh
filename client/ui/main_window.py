"""CueMesh Client main window."""
from __future__ import annotations
import asyncio
import logging
import sys
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QWidget,
    QVBoxLayout, QLabel, QStatusBar,
)

from client.mpv_controller import MpvController
from client.connection import ClientConnection
from client.ui.connect_screen import ConnectScreenWidget
from client.ui.playback_overlay import PlaybackOverlay
from client.ui.test_screen import TestScreen

logger = logging.getLogger("cuemesh.client.ui")


class _StateSignaler(QObject):
    state_changed = Signal(str)
    drift_updated = Signal(float)


class ClientMainWindow(QMainWindow):
    def __init__(self, loop: asyncio.AbstractEventLoop, mpv: MpvController):
        super().__init__()
        self.loop = loop
        self.mpv = mpv
        self._connection: Optional[ClientConnection] = None
        self._signaler = _StateSignaler()
        self._drift_ms = 0.0

        self.setWindowTitle("CueMesh Client")
        self.resize(800, 600)

        # Stacked widget: connect screen or waiting screen
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Connection screen
        self.connect_screen = ConnectScreenWidget(loop, self)
        self.connect_screen.connect_requested.connect(self._on_connect_requested)
        self.stack.addWidget(self.connect_screen)

        # Waiting/status screen (shown after connecting)
        self.status_widget = QWidget()
        status_layout = QVBoxLayout(self.status_widget)
        self.status_label = QLabel("Connecting...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 24px; color: #4CAF50;")
        status_layout.addWidget(self.status_label)
        self.stack.addWidget(self.status_widget)

        # Test screen (hidden initially)
        self.test_screen: Optional[TestScreen] = None

        # Overlay (hidden initially)
        self.overlay: Optional[PlaybackOverlay] = None

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Searching for controller...")

        # Shortcut: toggle overlay
        shortcut = QShortcut(QKeySequence("Ctrl+I"), self)
        shortcut.activated.connect(self._toggle_overlay)

        # Wire signals
        self._signaler.state_changed.connect(self._on_state_changed)
        self._signaler.drift_updated.connect(self._on_drift_updated)

    def _on_connect_requested(self, host: str, port: int) -> None:
        self.connect_screen.stop_discovery()
        self.stack.setCurrentWidget(self.status_widget)
        self.status_label.setText(f"Connecting to {host}:{port}...")
        self.status_bar.showMessage(f"Connecting to {host}:{port}...")

        # Create connection
        def on_state(state: str):
            self._signaler.state_changed.emit(state)

        self._connection = ClientConnection(
            self.mpv,
            on_state_change=on_state,
        )
        # Wire drift
        orig_send = self._connection._clock.send
        async def patched_send(msg_type, payload):
            if msg_type == "DRIFT":
                self._signaler.drift_updated.emit(float(payload.get("drift_ms", 0)))
            await orig_send(msg_type, payload)
        self._connection._clock.send = patched_send

        asyncio.run_coroutine_threadsafe(
            self._connection.connect(host, port), self.loop
        )

    def _on_state_changed(self, state: str) -> None:
        self.status_bar.showMessage(f"State: {state}")
        self.status_label.setText(f"State: {state}")
        if self.overlay:
            self.overlay.update_status(state, self._drift_ms)

    def _on_drift_updated(self, drift_ms: float) -> None:
        self._drift_ms = drift_ms
        if self.overlay:
            self.overlay.update_status(
                self._connection.state if self._connection else "idle",
                drift_ms
            )
        if self.test_screen and self.test_screen.isVisible():
            self.test_screen.update_drift(drift_ms)

    def _toggle_overlay(self) -> None:
        if self.overlay is None and self._connection:
            self.overlay = PlaybackOverlay(self._connection.client_id, parent=None)
        if self.overlay:
            self.overlay.toggle()
