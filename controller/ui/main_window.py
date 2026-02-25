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
        self.show_editor = ShowEditorWidget(state, self)
        self.run_mode = RunModeWidget(state, server, loop, self)
        self.client_manager = ClientManagerWidget(state, server, loop, self)
        self.diagnostics = DiagnosticsWidget(state, server, log_aggregator, loop, self)

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

        # Wire up signals (show editor and run mode need refresh on show load)
        # (these will be called via _on_show_loaded)

        # Heartbeat timer: update client status
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

        # Auto-load most recent show if available
        if self.state.recent_shows:
            recent_path = Path(self.state.recent_shows[0])
            if recent_path.exists():
                try:
                    self.state.load_show(recent_path)
                    self._on_show_loaded()
                    logger.info("Auto-loaded recent show: %s", recent_path)
                except Exception as e:
                    logger.warning("Failed to auto-load recent show: %s", e)

    def _setup_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")

        new_act = QAction("&New Show", self)
        new_act.triggered.connect(self._new_show)
        file_menu.addAction(new_act)

        open_act = QAction("&Open Show...", self)
        open_act.setShortcut(QKeySequence.Open)
        open_act.triggered.connect(self._open_show)
        file_menu.addAction(open_act)

        # Open Recent submenu
        self.recent_menu = file_menu.addMenu("Open &Recent")
        self._update_recent_menu()

        file_menu.addSeparator()

        save_act = QAction("&Save Show", self)
        save_act.setShortcut(QKeySequence.Save)
        save_act.triggered.connect(self._save_show)
        file_menu.addAction(save_act)

        save_as_act = QAction("Save &As...", self)
        save_as_act.triggered.connect(self._save_show_as)
        file_menu.addAction(save_as_act)

        file_menu.addSeparator()
        quit_act = QAction("&Quit", self)
        quit_act.setShortcut(QKeySequence.Quit)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

    def _on_show_loaded(self) -> None:
        title = self.state.show.title if self.state.show else "CueMesh Controller"
        self.setWindowTitle(f"CueMesh Controller — {title}")
        self.status.showMessage(f"Loaded: {self.state.show_path}")
        self.show_editor.refresh()
        self.run_mode.refresh()
        self._update_recent_menu()

    def _update_recent_menu(self) -> None:
        """Update the Open Recent submenu with recent shows."""
        self.recent_menu.clear()
        if not self.state.recent_shows:
            no_recent = QAction("No Recent Shows", self)
            no_recent.setEnabled(False)
            self.recent_menu.addAction(no_recent)
        else:
            for path_str in self.state.recent_shows:
                path = Path(path_str)
                action = QAction(path.name, self)
                action.setData(path_str)
                action.triggered.connect(lambda checked=False, p=path: self._open_recent(p))
                self.recent_menu.addAction(action)

    def _new_show(self) -> None:
        """Create a new show."""
        self.state.new_show()
        self._on_show_loaded()
        logger.info("Created new show")

    def _open_show(self) -> None:
        """Open a show file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Show", "", "CueMesh Shows (*.cuemesh.toml);;All Files (*)"
        )
        if path:
            self._load_show(Path(path))

    def _open_recent(self, path: Path) -> None:
        """Open a recent show."""
        if path.exists():
            self._load_show(path)
        else:
            QMessageBox.warning(self, "Not Found", f"File not found:\n{path}")

    def _load_show(self, path: Path) -> None:
        """Load a show from a path."""
        try:
            self.state.load_show(path)
            self._on_show_loaded()
            logger.info("Loaded show: %s", path)
        except Exception as e:
            logger.exception("Failed to load show")
            QMessageBox.critical(self, "Error", f"Failed to load show:\n{e}")

    def _save_show(self) -> None:
        """Save the current show."""
        if self.state.show is None:
            QMessageBox.information(self, "No Show", "No show is currently loaded.")
            return
        if self.state.show_path:
            try:
                self.state.save_show()
                self.status.showMessage(f"Saved: {self.state.show_path}")
                logger.info("Saved show: %s", self.state.show_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")
        else:
            self._save_show_as()

    def _save_show_as(self) -> None:
        """Save the current show as a new file."""
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
                self.status.showMessage(f"Saved: {path}")
                self._update_recent_menu()
                logger.info("Saved show as: %s", path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")

    def _tick(self) -> None:
        self.client_manager.refresh_clients()
        self.run_mode.refresh_status()
