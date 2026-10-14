"""Structured JSON logging. Never log secrets: callers pass only ids/metadata."""

import json
import logging
import sys
from datetime import UTC, datetime

from app.core.correlation import get_correlation_id

_RESERVED = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}
_SENSITIVE = ("token", "secret", "api_key", "password", "authorization", "cookie")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }
        for k, v in record.__dict__.items():
            if k not in _RESERVED:
                payload[k] = "[redacted]" if any(s in k.lower() for s in _SENSITIVE) else v
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
