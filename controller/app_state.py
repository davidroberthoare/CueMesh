"""CueMesh controller application state."""
from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from shared.show import Show, Cue

logger = logging.getLogger("cuemesh.controller.state")


@dataclass
class RunState:
    """Tracks run mode state."""
    current_cue_index: int = -1
    is_playing: bool = False
    is_paused: bool = False
    blackout: bool = False
    testscreen: bool = False
    master_start_utc_ms: int = 0

    @property
    def current_cue_id(self) -> Optional[str]:
        return None  # resolved by AppState


class AppState:
    """Central application state for the controller."""

    def __init__(self):
        self.show: Optional[Show] = None
        self.show_path: Optional[Path] = None
        self.run = RunState()
        self.recent_shows: list[str] = []
        self._recent_max = 10

    def load_show(self, path: Path) -> Show:
        from shared.show import load_show
        self.show = load_show(path)
        self.show_path = path
        self._add_recent(str(path))
        self.run = RunState()
        return self.show

    def save_show(self, path: Optional[Path] = None) -> None:
        from shared.show import save_show
        if self.show is None:
            return
        p = path or self.show_path
        if p is None:
            raise ValueError("No path specified for save")
        save_show(self.show, p)
        self.show_path = p
        self._add_recent(str(p))

    def new_show(self) -> Show:
        self.show = Show()
        self.show_path = None
        self.run = RunState()
        return self.show

    def _add_recent(self, path_str: str) -> None:
        if path_str in self.recent_shows:
            self.recent_shows.remove(path_str)
        self.recent_shows.insert(0, path_str)
        self.recent_shows = self.recent_shows[:self._recent_max]

    def current_cue(self) -> Optional[Cue]:
        if self.show is None or self.run.current_cue_index < 0:
            return None
        cues = self.show.cues
        if self.run.current_cue_index >= len(cues):
            return None
        return cues[self.run.current_cue_index]

    def next_cue(self) -> Optional[Cue]:
        if self.show is None:
            return None
        idx = self.run.current_cue_index + 1
        if idx < len(self.show.cues):
            return self.show.cues[idx]
        return None

    def go_next(self) -> Optional[Cue]:
        if self.show is None or not self.show.cues:
            return None
        self.run.current_cue_index = min(
            self.run.current_cue_index + 1, len(self.show.cues) - 1
        )
        return self.current_cue()

    def go_prev(self) -> Optional[Cue]:
        if self.show is None or not self.show.cues:
            return None
        self.run.current_cue_index = max(0, self.run.current_cue_index - 1)
        return self.current_cue()

    def go_first(self) -> Optional[Cue]:
        if self.show is None or not self.show.cues:
            return None
        self.run.current_cue_index = 0
        return self.current_cue()

    def jump_to_cue(self, cue_id: str) -> Optional[Cue]:
        if self.show is None:
            return None
        for i, cue in enumerate(self.show.cues):
            if cue.id == cue_id:
                self.run.current_cue_index = i
                return cue
        return None
