"""CueMesh show file (TOML) parsing and validation."""
from __future__ import annotations
import tomllib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import datetime
import re


@dataclass
class SyncCorrection:
    rate_min: float = 0.98
    rate_max: float = 1.02
    hard_seek_threshold_ms: int = 300
    sync_interval_ms: int = 1000


@dataclass
class SyncConfig:
    mode: str = "medium"
    max_drift_ms: int = 150
    start_lead_ms: int = 250
    correction: SyncCorrection = field(default_factory=SyncCorrection)


@dataclass
class ClientEntry:
    id: str = ""
    name: str = ""


@dataclass
class GlobalSettings:
    """Global show settings for defaults and display options."""
    fullscreen: bool = True
    default_volume: int = 100
    default_fade_in_ms: int = 0
    default_fade_out_ms: int = 0


@dataclass
class Cue:
    id: str = ""
    name: str = ""
    type: str = "video"  # "video" | "image"
    file: str = ""
    start_time_ms: int = 0
    end_time_ms: Optional[int] = None
    volume: int = 100
    loop: bool = False
    fade_in_ms: int = 0
    fade_out_ms: int = 0
    auto_follow_ms: Optional[int] = None
    notes: str = ""

    def validate(self) -> list[str]:
        errors = []
        if not self.id:
            errors.append("Cue missing 'id'")
        if not re.match(r'^[a-zA-Z0-9_\-]+$', self.id or "x"):
            errors.append(f"Cue id '{self.id}' contains invalid characters")
        if self.type not in ("video", "image"):
            errors.append(f"Cue '{self.id}': type must be 'video' or 'image'")
        if not self.file:
            errors.append(f"Cue '{self.id}': file is required")
        if not (0 <= self.volume <= 100):
            errors.append(f"Cue '{self.id}': volume must be 0-100")
        return errors


@dataclass
class Show:
    title: str = "Untitled Show"
    version: int = 1
    created_utc: str = ""
    modified_utc: str = ""
    media_root: str = "~/cuemesh_media"
    dropout_policy: str = "continue"  # "continue" | "freeze" | "black"
    sync: SyncConfig = field(default_factory=SyncConfig)
    settings: GlobalSettings = field(default_factory=GlobalSettings)
    clients: list[ClientEntry] = field(default_factory=list)
    cues: list[Cue] = field(default_factory=list)

    def validate(self) -> list[str]:
        errors = []
        if self.dropout_policy not in ("continue", "freeze", "black"):
            errors.append(f"Invalid dropout_policy: {self.dropout_policy}")
        if self.sync.mode != "medium":
            errors.append(f"Invalid sync.mode: {self.sync.mode}")
        ids_seen = set()
        for cue in self.cues:
            cue_errors = cue.validate()
            errors.extend(cue_errors)
            if cue.id in ids_seen:
                errors.append(f"Duplicate cue id: {cue.id}")
            ids_seen.add(cue.id)
        return errors

    def validate_media_paths(self, base_path: Path) -> list[tuple[str, str, bool]]:
        """Returns list of (cue_id, resolved_path, exists)."""
        media_root = (base_path / self.media_root).resolve()
        results = []
        for cue in self.cues:
            resolved = (media_root / cue.file).resolve()
            results.append((cue.id, str(resolved), resolved.exists()))
        return results


def _parse_sync(raw: dict) -> SyncConfig:
    correction_raw = raw.get("correction", {})
    correction = SyncCorrection(
        rate_min=correction_raw.get("rate_min", 0.98),
        rate_max=correction_raw.get("rate_max", 1.02),
        hard_seek_threshold_ms=correction_raw.get("hard_seek_threshold_ms", 300),
        sync_interval_ms=correction_raw.get("sync_interval_ms", 1000),
    )
    return SyncConfig(
        mode=raw.get("mode", "medium"),
        max_drift_ms=raw.get("max_drift_ms", 150),
        start_lead_ms=raw.get("start_lead_ms", 250),
        correction=correction,
    )


def _parse_cue(raw: dict) -> Cue:
    return Cue(
        id=raw.get("id", ""),
        name=raw.get("name", ""),
        type=raw.get("type", "video"),
        file=raw.get("file", ""),
        start_time_ms=raw.get("start_time_ms", 0),
        end_time_ms=raw.get("end_time_ms", None),
        volume=raw.get("volume", 100),
        loop=raw.get("loop", False),
        fade_in_ms=raw.get("fade_in_ms", 0),
        fade_out_ms=raw.get("fade_out_ms", 0),
        auto_follow_ms=raw.get("auto_follow_ms", None),
        notes=raw.get("notes", ""),
    )


def load_show(path: Path) -> Show:
    """Load a .cuemesh.toml show file."""
    with open(path, "rb") as f:
        data = tomllib.load(f)

    show_raw = data.get("show", {})
    sync_raw = show_raw.get("sync", {})
    settings_raw = show_raw.get("settings", {})
    clients_raw = data.get("clients", [])
    cues_raw = data.get("cues", [])

    settings = GlobalSettings(
        fullscreen=settings_raw.get("fullscreen", True),
        default_volume=settings_raw.get("default_volume", 100),
        default_fade_in_ms=settings_raw.get("default_fade_in_ms", 0),
        default_fade_out_ms=settings_raw.get("default_fade_out_ms", 0),
    )

    show = Show(
        title=show_raw.get("title", "Untitled Show"),
        version=show_raw.get("version", 1),
        created_utc=show_raw.get("created_utc", ""),
        modified_utc=show_raw.get("modified_utc", ""),
        media_root=show_raw.get("media_root", "~/cuemesh_media"),
        dropout_policy=show_raw.get("dropout_policy", "continue"),
        sync=_parse_sync(sync_raw),
        settings=settings,
        clients=[ClientEntry(id=c.get("id", ""), name=c.get("name", "")) for c in clients_raw],
        cues=[_parse_cue(c) for c in cues_raw],
    )
    return show


def save_show(show: Show, path: Path) -> None:
    """Save a Show object to a .cuemesh.toml file."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if not show.created_utc:
        show.created_utc = now
    show.modified_utc = now

    lines = []
    lines.append("[show]")
    lines.append(f'title = "{show.title}"')
    lines.append(f"version = {show.version}")
    lines.append(f'created_utc = "{show.created_utc}"')
    lines.append(f'modified_utc = "{show.modified_utc}"')
    lines.append(f'media_root = "{show.media_root}"')
    lines.append(f'dropout_policy = "{show.dropout_policy}"')
    lines.append("")
    lines.append("[show.sync]")
    lines.append(f'mode = "{show.sync.mode}"')
    lines.append(f"max_drift_ms = {show.sync.max_drift_ms}")
    lines.append(f"start_lead_ms = {show.sync.start_lead_ms}")
    lines.append("")
    lines.append("[show.sync.correction]")
    lines.append(f"rate_min = {show.sync.correction.rate_min}")
    lines.append(f"rate_max = {show.sync.correction.rate_max}")
    lines.append(f"hard_seek_threshold_ms = {show.sync.correction.hard_seek_threshold_ms}")
    lines.append(f"sync_interval_ms = {show.sync.correction.sync_interval_ms}")
    lines.append("")
    lines.append("[show.settings]")
    lines.append(f"fullscreen = {str(show.settings.fullscreen).lower()}")
    lines.append(f"default_volume = {show.settings.default_volume}")
    lines.append(f"default_fade_in_ms = {show.settings.default_fade_in_ms}")
    lines.append(f"default_fade_out_ms = {show.settings.default_fade_out_ms}")
    lines.append("")

    for client in show.clients:
        lines.append("[[clients]]")
        lines.append(f'id = "{client.id}"')
        lines.append(f'name = "{client.name}"')
        lines.append("")

    for cue in show.cues:
        lines.append("[[cues]]")
        lines.append(f'id = "{cue.id}"')
        lines.append(f'name = "{cue.name}"')
        lines.append(f'type = "{cue.type}"')
        lines.append(f'file = "{cue.file}"')
        lines.append(f"start_time_ms = {cue.start_time_ms}")
        if cue.end_time_ms is not None:
            lines.append(f"end_time_ms = {cue.end_time_ms}")
        lines.append(f"volume = {cue.volume}")
        lines.append(f"loop = {str(cue.loop).lower()}")
        lines.append(f"fade_in_ms = {cue.fade_in_ms}")
        lines.append(f"fade_out_ms = {cue.fade_out_ms}")
        if cue.auto_follow_ms is not None:
            lines.append(f"auto_follow_ms = {cue.auto_follow_ms}")
        if cue.notes:
            lines.append(f'notes = "{cue.notes}"')
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
