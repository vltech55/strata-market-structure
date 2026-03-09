"""JSON log formatter — structured logs for production aggregation (Loki/ELK/etc.)."""
from __future__ import annotations

import json
import logging
import sys
import traceback


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record."""

    _RESERVED = frozenset(
        {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename", "module",
            "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs",
            "relativeCreated", "thread", "threadName", "processName", "process",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Promote extra-fields onto the top-level (structlog-style ergonomics).
        for k, v in record.__dict__.items():
            if k not in self._RESERVED and not k.startswith("_"):
                payload[k] = v
        if record.exc_info:
            payload["exc"] = "".join(traceback.format_exception(*record.exc_info))
        try:
            return json.dumps(payload, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            # Fail-safe: never break logging itself.
            print(f"!! log serialise failure: {payload!r}", file=sys.stderr)
            return json.dumps({"ts": payload["ts"], "level": "ERROR", "msg": "log serialise failure"})
