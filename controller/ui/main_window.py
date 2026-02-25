"""CueMesh Controller main window."""
from __future__ import annotations
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, QThread, QObject
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QMessageBox, QStatusBar, QToolBar,
)

from controller.app_state import AppState
from controller.ui.show_manager import ShowManagerWidget
from controller.ui.show_editor import ShowEditorWidget
from controller.ui.run_mode import RunModeWidget
from controller.ui.client_manager import ClientManagerWidget
from controller.ui.diagnostics import DiagnosticsWidget

logger = logging.getLogger("cuemesh.controller.ui")


class MainWindow(QMainWindow):
    def __init__(self, state: AppState, server, log_aggregator, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.state = state
        self.server = server
        self.log_aggregator = log_aggregator
        self.loop = loop

        self.setWindowTitle("CueMesh Controller")
        self.resize(1400, 900)

        # Central tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Panels
        self.show_manager = ShowManagerWidget(state, self)
        self.show_editor = ShowEditorWidget(state, self)
        self.run_mode = RunModeWidget(state, server, loop, self)
        self.client_manager = ClientManagerWidget(state, server, loop, self)
        self.diagnostics = DiagnosticsWidget(state, server, log_aggregator, loop, self)

        self.tabs.addTab(self.show_manager, "Show Manager")
        self.tabs.addTab(self.show_editor, "Show Editor")
        self.tabs.addTab(self.run_mode, "Run Show")
        self.tabs.addTab(self.client_manager, "Clients")
        self.tabs.addTab(self.diagnostics, "Diagnostics")

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready")

        # Menu bar
        self._setup_menu()

        # Wire up signals
        self.show_manager.show_loaded.connect(self._on_show_loaded)
        self.show_manager.show_loaded.connect(self.show_editor.refresh)
        self.show_manager.show_loaded.connect(self.run_mode.refresh)

        # Heartbeat timer: update client status
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _setup_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")

        new_act = QAction("&New Show", self)
        new_act.triggered.connect(self.show_manager.new_show)
        file_menu.addAction(new_act)

        open_act = QAction("&Open Show...", self)
        open_act.setShortcut(QKeySequence.Open)
        open_act.triggered.connect(self.show_manager.open_show)
        file_menu.addAction(open_act)

        save_act = QAction("&Save Show", self)
        save_act.setShortcut(QKeySequence.Save)
        save_act.triggered.connect(self.show_manager.save_show)
        file_menu.addAction(save_act)

        file_menu.addSeparator()
        quit_act = QAction("&Quit", self)
        quit_act.setShortcut(QKeySequence.Quit)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

    def _on_show_loaded(self) -> None:
        title = self.state.show.title if self.state.show else "CueMesh Controller"
        self.setWindowTitle(f"CueMesh Controller — {title}")
        self.status.showMessage(f"Loaded: {self.state.show_path}")

    def _tick(self) -> None:
        self.client_manager.refresh_clients()
        self.run_mode.refresh_status()
