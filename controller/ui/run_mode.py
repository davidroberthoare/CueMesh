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
        self.btn_pause = QPushButton("PAUSE")
        self.btn_pause.setMinimumHeight(60)
        self.btn_pause.setStyleSheet("background-color: #FF9800; color: white;")
        self.btn_pause.clicked.connect(self._on_pause)
        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setMinimumHeight(60)
        self.btn_stop.setStyleSheet("background-color: #F44336; color: white;")
        self.btn_stop.clicked.connect(self._on_stop)
        for btn in [self.btn_prev, self.btn_pause, self.btn_stop]:
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

        # Playback timeline
        timeline_group = QGroupBox("Playback Timeline")
        timeline_layout = QVBoxLayout(timeline_group)
        
        timeline_info_row = QHBoxLayout()
        self.timeline_position_label = QLabel("0:00")
        self.timeline_duration_label = QLabel("0:00")
        timeline_info_row.addWidget(self.timeline_position_label)
        timeline_info_row.addStretch()
        timeline_info_row.addWidget(self.timeline_duration_label)
        timeline_layout.addLayout(timeline_info_row)
        
        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setRange(0, 1000)
        self.timeline_slider.setValue(0)
        self.timeline_slider.sliderPressed.connect(self._on_timeline_pressed)
        self.timeline_slider.sliderReleased.connect(self._on_timeline_released)
        self.timeline_slider.sliderMoved.connect(self._on_timeline_moved)
        timeline_layout.addWidget(self.timeline_slider)
        
        self._timeline_dragging = False
        self._timeline_duration_ms = 0
        
        layout.addWidget(timeline_group)

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
            # Update server with show settings
            self.server.set_show_settings(self.state.show.settings)
            for cue in self.state.show.cues:
                self.cue_selector.addItem(f"[{cue.id}] {cue.name}", cue.id)
        self._update_cue_labels()

    def refresh_status(self) -> None:
        """Called periodically to update client status display."""
        self.status_list.clear()
        max_position_ms = 0
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
                max_position_ms = max(max_position_ms, session.position_ms)
        
        # Update timeline
        if not self._timeline_dragging:
            self._update_timeline_position(max_position_ms)
        
        self._update_cue_labels()

    def _update_cue_labels(self) -> None:
        cur = self.state.current_cue()
        nxt = self.state.next_cue()
        self.lbl_current.setText(f"CURRENT: {cur.name if cur else '—'}")
        self.lbl_next.setText(f"NEXT: {nxt.name if nxt else '—'}")
        
        # Update timeline duration based on current cue
        if cur:
            # Calculate duration from cue data
            if cur.end_time_ms is not None:
                self._timeline_duration_ms = cur.end_time_ms - cur.start_time_ms
            else:
                # If no end time, try to estimate from file metadata or default to large value
                self._timeline_duration_ms = 300000  # Default 5 minutes
            self.timeline_slider.setRange(0, self._timeline_duration_ms)
        else:
            self._timeline_duration_ms = 0
            self.timeline_slider.setRange(0, 1000)
        
        # Update duration label
        self.timeline_duration_label.setText(self._format_time_ms(self._timeline_duration_ms))

    def _on_go(self) -> None:
        """GO button: advance to next cue and play it."""
        if self.state.show is None or not self.state.show.cues:
            return
        # Advance to next cue
        cue = self.state.go_next()
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

    def _on_prev(self) -> None:
        cue = self.state.go_prev()
        if cue:
            lead_ms = self.state.show.sync.start_lead_ms if self.state.show else 250
            asyncio.run_coroutine_threadsafe(self._do_go(cue, lead_ms), self.loop)
        self._update_cue_labels()

    def _on_pause(self) -> None:
        asyncio.run_coroutine_threadsafe(self.server.send_pause(), self.loop)

    def _on_stop(self) -> None:
        """STOP button: stop playback and go to black."""
        asyncio.run_coroutine_threadsafe(self.server.send_stop(), self.loop)
        asyncio.run_coroutine_threadsafe(self.server.send_blackout(True), self.loop)

    def _on_jump(self) -> None:
        cue_id = self.cue_selector.currentData()
        if cue_id:
            cue = self.state.jump_to_cue(cue_id)
            if cue:
                lead_ms = self.state.show.sync.start_lead_ms if self.state.show else 250
                asyncio.run_coroutine_threadsafe(self._do_go(cue, lead_ms), self.loop)
        self._update_cue_labels()

    def _on_timeline_pressed(self) -> None:
        """User started dragging the timeline slider."""
        self._timeline_dragging = True

    def _on_timeline_moved(self, value: int) -> None:
        """User is dragging the timeline slider."""
        # Update position label while dragging
        self.timeline_position_label.setText(self._format_time_ms(value))

    def _on_timeline_released(self) -> None:
        """User released the timeline slider - seek to that position."""
        self._timeline_dragging = False
        position_ms = self.timeline_slider.value()
        asyncio.run_coroutine_threadsafe(self.server.send_seek(position_ms), self.loop)

    def _update_timeline_position(self, position_ms: int) -> None:
        """Update timeline slider and label based on current position."""
        self.timeline_slider.setValue(min(position_ms, self._timeline_duration_ms))
        self.timeline_position_label.setText(self._format_time_ms(position_ms))

    def _format_time_ms(self, ms: int) -> str:
        """Format milliseconds as MM:SS."""
        total_seconds = ms // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}"
