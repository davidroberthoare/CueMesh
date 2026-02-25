"""CueMesh file hashing utilities for preflight validation."""
from __future__ import annotations
import hashlib
from pathlib import Path


def sha256_file(path: Path, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def build_media_manifest(media_root: Path, cue_files: list[str]) -> dict[str, str | None]:
    """
    Returns dict mapping relative_path -> sha256_hex (or None if missing).
    """
    manifest = {}
    for rel in cue_files:
        p = (media_root / rel).resolve()
        if p.exists():
            manifest[rel] = sha256_file(p)
        else:
            manifest[rel] = None
    return manifest
