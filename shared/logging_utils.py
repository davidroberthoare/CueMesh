"""CueMesh logging utilities."""
from __future__ import annotations
import logging
import logging.handlers
import json
import time
from pathlib import Path


def setup_rotating_logger(name: str, log_dir: Path, level: int = logging.DEBUG) -> logging.Logger:
    """Set up a rotating file logger + console output."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{name}.log"

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        # Rotating file handler: 5MB x 5 files
        fh = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        fh.setLevel(level)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    return logger


def log_jsonl(log_dir: Path, record: dict) -> None:
    """Append a JSONL log record to a daily log file."""
    log_dir.mkdir(parents=True, exist_ok=True)
    date_str = time.strftime("%Y-%m-%d")
    log_file = log_dir / f"cuemesh-{date_str}.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
