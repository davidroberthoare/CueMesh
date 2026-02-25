"""Tests for file hashing utilities."""
import pytest
import tempfile
import os
from pathlib import Path
from shared.hashing import sha256_file, build_media_manifest

# hashlib.sha256(b"hello world").hexdigest()
HELLO_WORLD_SHA256 = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


def test_sha256_file_known():
    with tempfile.NamedTemporaryFile(delete=False, mode="wb") as f:
        f.write(b"hello world")
        path = Path(f.name)
    try:
        result = sha256_file(path)
        assert result == HELLO_WORLD_SHA256
        assert len(result) == 64
    finally:
        os.unlink(path)


def test_sha256_file_consistency():
    with tempfile.NamedTemporaryFile(delete=False, mode="wb") as f:
        f.write(b"test content for hashing")
        path = Path(f.name)
    try:
        r1 = sha256_file(path)
        r2 = sha256_file(path)
        assert r1 == r2
    finally:
        os.unlink(path)


def test_build_media_manifest_existing():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "video.webm").write_bytes(b"fake video")
        (root / "image.png").write_bytes(b"fake image")
        manifest = build_media_manifest(root, ["video.webm", "image.png"])
        assert manifest["video.webm"] is not None
        assert manifest["image.png"] is not None
        assert len(manifest["video.webm"]) == 64


def test_build_media_manifest_missing():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        manifest = build_media_manifest(root, ["missing.webm"])
        assert manifest["missing.webm"] is None


def test_build_media_manifest_mixed():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "exists.webm").write_bytes(b"data")
        manifest = build_media_manifest(root, ["exists.webm", "missing.png"])
        assert manifest["exists.webm"] is not None
        assert manifest["missing.png"] is None
