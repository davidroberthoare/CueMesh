"""CueMesh log aggregation and support bundle export."""
from __future__ import annotations
import io
import json
import logging
import platform
import sys
import time
import zipfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger("cuemesh.controller.logs")


class LogAggregator:
    """Collects logs from controller and connected clients."""

    MAX_CLIENT_LOGS = 5000  # max lines per client kept in memory

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._client_logs: dict[str, list[dict]] = {}  # client_id -> log records

    def add_client_log(self, client_id: str, record: dict) -> None:
        buf = self._client_logs.setdefault(client_id, [])
        buf.append(record)
        if len(buf) > self.MAX_CLIENT_LOGS:
            buf.pop(0)

    def export_bundle(self, show_path: Optional[Path] = None) -> bytes:
        """Build a zip support bundle and return as bytes."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # System info
            sysinfo = {
                "platform": platform.platform(),
                "python": sys.version,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            zf.writestr("system_info.json", json.dumps(sysinfo, indent=2))

            # Show file
            if show_path and show_path.exists():
                zf.write(show_path, f"show/{show_path.name}")

            # Controller logs
            if self.log_dir.exists():
                for log_file in sorted(self.log_dir.glob("*.log")):
                    zf.write(log_file, f"controller_logs/{log_file.name}")
                for log_file in sorted(self.log_dir.glob("*.jsonl")):
                    zf.write(log_file, f"controller_logs/{log_file.name}")

            # Client logs
            for client_id, records in self._client_logs.items():
                lines = "\n".join(json.dumps(r) for r in records)
                zf.writestr(f"client_logs/{client_id}.jsonl", lines)

        return buf.getvalue()
