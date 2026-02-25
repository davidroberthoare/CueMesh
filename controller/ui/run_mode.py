"""CueMesh Run Mode panel — GO, Next/Prev, Blackout, Jog."""
from __future__ import annotations
import asyncio
import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSlider, QGroupBox, QListWidget, QListWidgetItem, QComboBox,
    QSizePolicy,
)

from controller.app_state import AppState
from shared.protocol import MSG_PLAY_AT, MSG_PAUSE, MSG_STOP, MSG_BLACKOUT

logger = logging.getLogger("cuemesh.controller.ui.run")


class RunModeWidget(QWidget):
    def __init__(self, state: AppState, server, loop: asyncio.AbstractEventLoop, parent=None):
        super().__init__(parent)
        self.state = state
        self.server = server
        self.loop = loop
        self._jog_timer = QTimer()
        self._jog_timer.timeout.connect(self._jog_tick)
        self._jog_direction = 0  # -1 backward, 1 forward
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Current / Next cue info
        info_row = QHBoxLayout()
        self.lbl_current = QLabel("CURRENT: —")
        self.lbl_current.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.lbl_next = QLabel("NEXT: —")
        self.lbl_next.setStyleSheet("font-size: 14px; color: #888;")
        info_row.addWidget(self.lbl_current)
        info_row.addStretch()
        info_row.addWidget(self.lbl_next)
        layout.addLayout(info_row)

        # Big GO button
        self.btn_go = QPushButton("GO")
        self.btn_go.setMinimumHeight(120)
        font = QFont()
        font.setPointSize(48)
        font.setBold(True)
        self.btn_go.setFont(font)
        self.btn_go.setStyleSheet("background-color: #4CAF50; color: white; border-radius: 8px;")
        self.btn_go.clicked.connect(self._on_go)
        layout.addWidget(self.btn_go)

        # Nav buttons
        nav_row = QHBoxLayout()
        self.btn_prev = QPushButton("◀ PREV")
        self.btn_prev.setMinimumHeight(60)
        self.btn_prev.clicked.connect(self._on_prev)
        self.btn_next = QPushButton("NEXT ▶")
        self.btn_next.setMinimumHeight(60)
        self.btn_next.clicked.connect(self._on_next)
        self.btn_pause = QPushButton("PAUSE")
        self.btn_pause.setMinimumHeight(60)
        self.btn_pause.setStyleSheet("background-color: #FF9800; color: white;")
        self.btn_pause.clicked.connect(self._on_pause)
        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setMinimumHeight(60)
        self.btn_stop.setStyleSheet("background-color: #F44336; color: white;")
        self.btn_stop.clicked.connect(self._on_stop)
        for btn in [self.btn_prev, self.btn_next, self.btn_pause, self.btn_stop]:
            nav_row.addWidget(btn)
        layout.addLayout(nav_row)

        # Jump to cue
        jump_row = QHBoxLayout()
        self.cue_selector = QComboBox()
        self.cue_selector.setMinimumWidth(300)
        self.btn_jump = QPushButton("Jump to Cue")
        self.btn_jump.clicked.connect(self._on_jump)
        jump_row.addWidget(QLabel("Jump:"))
        jump_row.addWidget(self.cue_selector)
        jump_row.addWidget(self.btn_jump)
        jump_row.addStretch()
        layout.addLayout(jump_row)

        # Blackout toggle
        ctl_row = QHBoxLayout()
        self.btn_blackout = QPushButton("BLACKOUT")
        self.btn_blackout.setCheckable(True)
        self.btn_blackout.setMinimumHeight(50)
        self.btn_blackout.setStyleSheet("background-color: #212121; color: white;")
        self.btn_blackout.clicked.connect(self._on_blackout)
        ctl_row.addWidget(self.btn_blackout)

        # Jog controls
        jog_group = QGroupBox("Jog / Rate")
        jog_layout = QHBoxLayout(jog_group)
        self.btn_jog_back = QPushButton("◀◀ JOG")
        self.btn_jog_back.setCheckable(True)
        self.btn_jog_back.pressed.connect(lambda: self._start_jog(-1))
        self.btn_jog_back.released.connect(self._stop_jog)
        self.btn_jog_fwd = QPushButton("JOG ▶▶")
        self.btn_jog_fwd.setCheckable(True)
        self.btn_jog_fwd.pressed.connect(lambda: self._start_jog(1))
        self.btn_jog_fwd.released.connect(self._stop_jog)
        self.rate_slider = QSlider(Qt.Horizontal)
        self.rate_slider.setRange(50, 200)
        self.rate_slider.setValue(100)
        self.rate_label = QLabel("Rate: 1.0x")
        self.rate_slider.valueChanged.connect(self._on_rate_changed)
        jog_layout.addWidget(self.btn_jog_back)
        jog_layout.addWidget(self.rate_slider)
        jog_layout.addWidget(self.rate_label)
        jog_layout.addWidget(self.btn_jog_fwd)
        ctl_row.addWidget(jog_group)

        layout.addLayout(ctl_row)

        # Client status mini-view
        status_group = QGroupBox("Client Status")
        status_layout = QVBoxLayout(status_group)
        self.status_list = QListWidget()
        self.status_list.setMaximumHeight(150)
        status_layout.addWidget(self.status_list)
        layout.addWidget(status_group)

    def refresh(self) -> None:
        """Refresh cue list after show load."""
        self.cue_selector.clear()
        if self.state.show:
            for cue in self.state.show.cues:
                self.cue_selector.addItem(f"[{cue.id}] {cue.name}", cue.id)
        self._update_cue_labels()

    def refresh_status(self) -> None:
        """Called periodically to update client status display."""
        self.status_list.clear()
        for cid, session in self.server.clients.items():
            if session.is_accepted:
                age = session.heartbeat_age
                age_str = f"{age:.0f}s ago"
                drift_str = f"drift:{session.drift_ms:.0f}ms"
                item_text = f"{session.name}: {session.state} | pos:{session.position_ms}ms | {drift_str} | hb:{age_str}"
                item = QListWidgetItem(item_text)
                if age > 10:
                    item.setForeground(Qt.red)
                self.status_list.addItem(item)
        self._update_cue_labels()

    def _update_cue_labels(self) -> None:
        cur = self.state.current_cue()
        nxt = self.state.next_cue()
        self.lbl_current.setText(f"CURRENT: {cur.name if cur else '—'}")
        self.lbl_next.setText(f"NEXT: {nxt.name if nxt else '—'}")

    def _on_go(self) -> None:
        if self.state.show is None or not self.state.show.cues:
            return
        if self.state.run.current_cue_index < 0:
            self.state.go_first()
        cue = self.state.current_cue()
        if cue is None:
            return
        lead_ms = self.state.show.sync.start_lead_ms
        asyncio.run_coroutine_threadsafe(
            self._do_go(cue, lead_ms), self.loop
        )
        self._update_cue_labels()

    async def _do_go(self, cue, lead_ms: int) -> None:
        await self.server.send_load_cue(cue)
        await asyncio.sleep(lead_ms / 1000.0 * 0.5)
        await self.server.send_play_at(cue.id, lead_ms)

    def _on_next(self) -> None:
        cue = self.state.go_next()
        if cue:
            lead_ms = self.state.show.sync.start_lead_ms if self.state.show else 250
            asyncio.run_coroutine_threadsafe(self._do_go(cue, lead_ms), self.loop)
        self._update_cue_labels()

    def _on_prev(self) -> None:
        cue = self.state.go_prev()
        if cue:
            lead_ms = self.state.show.sync.start_lead_ms if self.state.show else 250
            asyncio.run_coroutine_threadsafe(self._do_go(cue, lead_ms), self.loop)
        self._update_cue_labels()

    def _on_pause(self) -> None:
        asyncio.run_coroutine_threadsafe(self.server.send_pause(), self.loop)

    def _on_stop(self) -> None:
        asyncio.run_coroutine_threadsafe(self.server.send_stop(), self.loop)

    def _on_blackout(self, checked: bool) -> None:
        asyncio.run_coroutine_threadsafe(self.server.send_blackout(checked), self.loop)
        style = "background-color: #F44336; color: white;" if checked else "background-color: #212121; color: white;"
        self.btn_blackout.setStyleSheet(style)

    def _on_jump(self) -> None:
        cue_id = self.cue_selector.currentData()
        if cue_id:
            cue = self.state.jump_to_cue(cue_id)
            if cue:
                lead_ms = self.state.show.sync.start_lead_ms if self.state.show else 250
                asyncio.run_coroutine_threadsafe(self._do_go(cue, lead_ms), self.loop)
        self._update_cue_labels()

    def _on_rate_changed(self, value: int) -> None:
        rate = value / 100.0
        self.rate_label.setText(f"Rate: {rate:.2f}x")
        asyncio.run_coroutine_threadsafe(self.server.send_set_rate(rate), self.loop)

    def _start_jog(self, direction: int) -> None:
        self._jog_direction = direction
        self._jog_timer.start(100)

    def _stop_jog(self) -> None:
        self._jog_timer.stop()
        self._jog_direction = 0

    def _jog_tick(self) -> None:
        if self._jog_direction > 0:
            asyncio.run_coroutine_threadsafe(self.server.send_set_rate(2.0), self.loop)
        elif self._jog_direction < 0:
            # Backward jog: seek backward repeatedly
            asyncio.run_coroutine_threadsafe(self._backward_jog(), self.loop)

    async def _backward_jog(self) -> None:
        # Seek back 200ms as jog step
        await self.server.broadcast_accepted("SEEK_RELATIVE", {"delta_ms": -200})
