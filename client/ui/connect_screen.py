"""CueMesh Client connection/discovery screen."""
from __future__ import annotations
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QLineEdit, QGroupBox,
    QFormLayout, QSpinBox,
)

from client.discovery_browser import DiscoveryBrowser, DiscoveredController

logger = logging.getLogger("cuemesh.client.ui.connect")

CONFIG_FILE = Path.home() / ".cuemesh" / "client_config.json"


class ConnectScreenWidget(QWidget):
    connect_requested = Signal(str, int)  # host, port
    _controller_discovered = Signal(object)  # DiscoveredController

    def __init__(self, loop: asyncio.AbstractEventLoop, parent=None):
        super().__init__(parent)
        self.loop = loop
        self._browser: Optional[DiscoveryBrowser] = None
        self._setup_ui()
        self._controller_discovered.connect(self._add_discovered)
        self._start_discovery()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        title = QLabel("CueMesh Client")
        title.setStyleSheet("font-size: 32px; font-weight: bold; color: #2196F3;")
        layout.addWidget(title)

        subtitle = QLabel("Searching for controller on local network...")
        subtitle.setStyleSheet("font-size: 14px; color: #888;")
        self.subtitle = subtitle
        layout.addWidget(subtitle)

        # Discovered controllers
        disco_group = QGroupBox("Discovered Controllers")
        disco_layout = QVBoxLayout(disco_group)
        self.disco_list = QListWidget()
        self.disco_list.setMinimumHeight(150)
        disco_layout.addWidget(self.disco_list)

        self.btn_connect_discovered = QPushButton("Connect to Selected")
        self.btn_connect_discovered.setMinimumHeight(44)
        self.btn_connect_discovered.clicked.connect(self._connect_discovered)
        disco_layout.addWidget(self.btn_connect_discovered)
        layout.addWidget(disco_group)

        # Manual entry
        manual_group = QGroupBox("Manual Connection")
        manual_layout = QFormLayout(manual_group)
        self.fld_host = QLineEdit()
        self.fld_host.setPlaceholderText("192.168.1.100")
        self.fld_port = QSpinBox()
        self.fld_port.setRange(1, 65535)
        self.fld_port.setValue(9420)
        manual_layout.addRow("Host:", self.fld_host)
        manual_layout.addRow("Port:", self.fld_port)
        self.btn_connect_manual = QPushButton("Connect")
        self.btn_connect_manual.setMinimumHeight(44)
        self.btn_connect_manual.clicked.connect(self._connect_manual)
        manual_layout.addRow(self.btn_connect_manual)
        layout.addWidget(manual_group)

        layout.addStretch()

    def _start_discovery(self) -> None:
        def on_found(dc: DiscoveredController) -> None:
            # Emit signal to marshal to Qt thread
            self._controller_discovered.emit(dc)

        self._browser = DiscoveryBrowser(on_found=on_found)
        asyncio.run_coroutine_threadsafe(self._browser.start(), self.loop)

    def _add_discovered(self, dc: DiscoveredController) -> None:
        label = f"{dc.host}:{dc.port}"
        if dc.show_title:
            label += f" — {dc.show_title}"
        # Check not already in list
        for i in range(self.disco_list.count()):
            if self.disco_list.item(i).text().startswith(f"{dc.host}:{dc.port}"):
                return
        item = QListWidgetItem(label)
        item.setData(Qt.UserRole, (dc.host, dc.port))
        self.disco_list.addItem(item)
        self.subtitle.setText(f"Found {self.disco_list.count()} controller(s)")

    def _connect_discovered(self) -> None:
        item = self.disco_list.currentItem()
        if not item:
            return
        host, port = item.data(Qt.UserRole)
        self._save_connection(host, port)
        self.connect_requested.emit(host, port)

    def _connect_manual(self) -> None:
        host = self.fld_host.text().strip()
        port = self.fld_port.value()
        if host:
            self._save_connection(host, port)
            self.connect_requested.emit(host, port)

    def _save_connection(self, host: str, port: int) -> None:
        """Save last connection to config file."""
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            config = {"last_host": host, "last_port": port}
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=2)
            logger.info("Saved connection: %s:%d", host, port)
        except Exception as e:
            logger.warning("Failed to save connection config: %s", e)

    def get_last_connection(self) -> Optional[tuple[str, int]]:
        """Load last connection from config file."""
        if not CONFIG_FILE.exists():
            return None
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
            host = config.get("last_host")
            port = config.get("last_port")
            if host and port:
                logger.info("Loaded last connection: %s:%d", host, port)
                return (host, port)
        except Exception as e:
            logger.warning("Failed to load connection config: %s", e)
        return None

    def stop_discovery(self) -> None:
        if self._browser:
            asyncio.run_coroutine_threadsafe(self._browser.stop(), self.loop)
