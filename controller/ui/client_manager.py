"""CueMesh Client Manager panel."""
from __future__ import annotations
import asyncio
import logging
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QInputDialog,
    QGroupBox, QAbstractItemView,
)

from controller.app_state import AppState

logger = logging.getLogger("cuemesh.controller.ui.clients")


class ClientManagerWidget(QWidget):
    def __init__(self, state: AppState, server, loop: asyncio.AbstractEventLoop, parent=None):
        super().__init__(parent)
        self.state = state
        self.server = server
        self.loop = loop
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Client Manager")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # Pending clients table
        pending_group = QGroupBox("Pending Clients")
        pending_layout = QVBoxLayout(pending_group)
        self.pending_table = QTableWidget(0, 4)
        self.pending_table.setHorizontalHeaderLabels(["Client ID", "Hostname", "Platform", "Action"])
        self.pending_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pending_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        pending_layout.addWidget(self.pending_table)

        pending_btns = QHBoxLayout()
        self.btn_accept = QPushButton("Accept Selected")
        self.btn_reject = QPushButton("Reject Selected")
        self.btn_accept.clicked.connect(self._accept_selected)
        self.btn_reject.clicked.connect(self._reject_selected)
        pending_btns.addWidget(self.btn_accept)
        pending_btns.addWidget(self.btn_reject)
        pending_layout.addLayout(pending_btns)
        layout.addWidget(pending_group)

        # Accepted clients table
        accepted_group = QGroupBox("Accepted Clients")
        accepted_layout = QVBoxLayout(accepted_group)
        self.accepted_table = QTableWidget(0, 8)
        self.accepted_table.setHorizontalHeaderLabels([
            "Name", "Client ID", "State", "Cue", "Pos (ms)", "Drift (ms)", "Heartbeat", "Error"
        ])
        self.accepted_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.accepted_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        accepted_layout.addWidget(self.accepted_table)

        accepted_btns = QHBoxLayout()
        self.btn_rename = QPushButton("Rename Client")
        self.btn_rename.clicked.connect(self._rename_client)
        accepted_btns.addWidget(self.btn_rename)
        accepted_btns.addStretch()
        accepted_layout.addLayout(accepted_btns)
        layout.addWidget(accepted_group)

    def refresh_clients(self) -> None:
        """Refresh both tables from server state."""
        pending = [(cid, s) for cid, s in self.server.clients.items() if s.status == "pending"]
        accepted = [(cid, s) for cid, s in self.server.clients.items() if s.status == "accepted"]

        # Pending
        self.pending_table.setRowCount(len(pending))
        for row, (cid, s) in enumerate(pending):
            self.pending_table.setItem(row, 0, QTableWidgetItem(cid[:16]))
            self.pending_table.setItem(row, 1, QTableWidgetItem(s.hostname))
            self.pending_table.setItem(row, 2, QTableWidgetItem(s.platform))
            self.pending_table.setItem(row, 3, QTableWidgetItem("Pending"))

        # Accepted
        self.accepted_table.setRowCount(len(accepted))
        for row, (cid, s) in enumerate(accepted):
            age = s.heartbeat_age
            age_str = f"{age:.1f}s"
            self.accepted_table.setItem(row, 0, QTableWidgetItem(s.name))
            self.accepted_table.setItem(row, 1, QTableWidgetItem(cid[:16]))
            self.accepted_table.setItem(row, 2, QTableWidgetItem(s.state))
            self.accepted_table.setItem(row, 3, QTableWidgetItem(s.cue_id or ""))
            self.accepted_table.setItem(row, 4, QTableWidgetItem(str(s.position_ms)))
            self.accepted_table.setItem(row, 5, QTableWidgetItem(f"{s.drift_ms:.1f}"))
            self.accepted_table.setItem(row, 6, QTableWidgetItem(age_str))
            self.accepted_table.setItem(row, 7, QTableWidgetItem(s.last_error or ""))
            if age > 10:
                for col in range(8):
                    item = self.accepted_table.item(row, col)
                    if item:
                        item.setForeground(Qt.red)

    def _accept_selected(self) -> None:
        rows = set(idx.row() for idx in self.pending_table.selectedIndexes())
        pending = [(cid, s) for cid, s in self.server.clients.items() if s.status == "pending"]
        for row in rows:
            if row < len(pending):
                cid, _ = pending[row]
                asyncio.run_coroutine_threadsafe(
                    self.server.accept_client(cid), self.loop
                )

    def _reject_selected(self) -> None:
        rows = set(idx.row() for idx in self.pending_table.selectedIndexes())
        pending = [(cid, s) for cid, s in self.server.clients.items() if s.status == "pending"]
        for row in rows:
            if row < len(pending):
                cid, _ = pending[row]
                asyncio.run_coroutine_threadsafe(
                    self.server.reject_client(cid), self.loop
                )

    def _rename_client(self) -> None:
        rows = set(idx.row() for idx in self.accepted_table.selectedIndexes())
        if not rows:
            return
        accepted = [(cid, s) for cid, s in self.server.clients.items() if s.status == "accepted"]
        row = next(iter(rows))
        if row < len(accepted):
            cid, session = accepted[row]
            new_name, ok = QInputDialog.getText(self, "Rename Client", "New name:", text=session.name)
            if ok and new_name.strip():
                session.name = new_name.strip()
                self.refresh_clients()
