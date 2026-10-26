"""Structured (JSON lines) logging for Tamarack tools.

Logs go to stderr, which systemd/journald captures for services and which
`tamarack-center` redirects to ``~/.local/state/tamarack/tamarack.log``.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

_STANDARD = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "tamarack"


def setup(verbose: bool = False, log_file: Path | None = None) -> None:
    root = logging.getLogger("tamarack")
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    root.handlers.clear()
    stream = logging.StreamHandler()
    stream.setFormatter(JsonFormatter())
    stream.setLevel(logging.DEBUG if verbose else logging.WARNING)
    root.addHandler(stream)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
