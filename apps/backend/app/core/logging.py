"""Compact tagged logging: `12:00:01 INFO  [AI] Request started provider=mock`.

Modules get a logger via `get_logger("ai")`; the tag is derived from the logger name.
Structured fields are passed through `extra={"fields": {...}}` and rendered as key=value.
"""

import logging
from typing import Any

ROOT_LOGGER_NAME = "waifu"


class TaggedFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        tag = record.name.removeprefix(f"{ROOT_LOGGER_NAME}.").upper()
        fields: dict[str, Any] = getattr(record, "fields", {}) or {}
        suffix = "".join(f" {key}={value}" for key, value in fields.items())
        time = self.formatTime(record, "%H:%M:%S")
        line = f"{time} {record.levelname:<5} [{tag}] {record.getMessage()}{suffix}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(TaggedFormatter())
    root = logging.getLogger(ROOT_LOGGER_NAME)
    root.handlers = [handler]
    root.setLevel(level.upper())
    root.propagate = False


def get_logger(tag: str) -> logging.Logger:
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{tag}")
