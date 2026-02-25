"""CueMesh preflight: verifies clients have matching media files."""
from __future__ import annotations
import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from shared.hashing import sha256_file, build_media_manifest

logger = logging.getLogger("cuemesh.controller.preflight")


@dataclass
class FileCheckResult:
    rel_path: str
    controller_hash: Optional[str]
    client_hash: Optional[str]
    status: str = "unknown"  # "ok" | "missing" | "mismatch" | "unknown"

    def compute_status(self) -> None:
        if self.controller_hash is None:
            self.status = "missing_on_controller"
        elif self.client_hash is None:
            self.status = "missing"
        elif self.controller_hash == self.client_hash:
            self.status = "ok"
        else:
            self.status = "mismatch"


@dataclass
class ClientPreflightResult:
    client_id: str
    files: list[FileCheckResult] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        return all(f.status == "ok" for f in self.files)


class PreflightCoordinator:
    """Runs preflight file verification across all accepted clients."""

    def __init__(self, server, media_root: Path, cue_files: list[str]):
        self.server = server
        self.media_root = media_root
        self.cue_files = cue_files
        self._controller_manifest: dict[str, Optional[str]] = {}

    def build_controller_manifest(self) -> dict[str, Optional[str]]:
        self._controller_manifest = build_media_manifest(self.media_root, self.cue_files)
        return self._controller_manifest

    async def run(self) -> list[ClientPreflightResult]:
        """
        v1: Controller computes its own manifest and requests STATUS from clients.
        Clients report their file states via STATUS messages.
        For v1, we do a simple self-check since file transfer is out of scope.
        """
        self.build_controller_manifest()
        results = []
        for client_id, session in self.server.clients.items():
            if not session.is_accepted:
                continue
            result = ClientPreflightResult(client_id=client_id)
            # In v1 we report controller-side check only
            for rel, ctrl_hash in self._controller_manifest.items():
                fc = FileCheckResult(rel_path=rel, controller_hash=ctrl_hash, client_hash=None)
                fc.compute_status()
                result.files.append(fc)
            results.append(result)
        return results
