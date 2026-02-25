"""Structured domain logging for CocoSearch.

Provides a category-aware logger (cs_log) that pushes structured LogEntry
records to the LogBuffer for unified output across web dashboard, terminal,
and log file. Falls back to Python logging when no buffer is initialized.
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any

from cocosearch.mcp.log_stream import LogBuffer, LogEntry, get_log_buffer

_MAX_FIELD_VALUE_LEN = 500

logger = logging.getLogger("cocosearch")


class LogCategory(str, Enum):
    SEARCH = "search"
    INDEX = "index"
    MCP = "mcp"
    CACHE = "cache"
    INFRA = "infra"
    SYSTEM = "system"
    DEPS = "deps"


class CsLog:
    """Domain logger with category-specific methods.

    Each method (search, index, mcp, cache, infra, system, deps) creates
    a structured LogEntry with the corresponding category and pushes it
    to the LogBuffer. Falls back to Python logging if no buffer is available.
    """

    def __init__(self, buffer: LogBuffer | None = None) -> None:
        self._buffer = buffer

    def _get_buffer(self) -> LogBuffer | None:
        return self._buffer or get_log_buffer()

    def _emit(self, category: LogCategory, message: str, level: str, fields: dict[str, Any]) -> None:
        # Truncate long field values
        truncated: dict[str, Any] = {}
        for k, v in fields.items():
            sv = str(v)
            if len(sv) > _MAX_FIELD_VALUE_LEN:
                truncated[k] = sv[:_MAX_FIELD_VALUE_LEN]
            else:
                truncated[k] = v

        cat_value = category.value
        buf = self._get_buffer()
        if buf is not None:
            entry = LogEntry(
                timestamp=time.time(),
                level=level,
                category=cat_value,
                message=message,
                fields=truncated,
            )
            buf.append(entry)
        else:
            # Fallback to Python logging
            fields_str = " ".join(f"{k}={v}" for k, v in truncated.items())
            log_msg = f"[{cat_value}] {message}"
            if fields_str:
                log_msg += f"  {fields_str}"
            py_level = getattr(logging, level, logging.INFO)
            logger.log(py_level, log_msg)

    def search(self, message: str, *, level: str = "INFO", **fields: Any) -> None:
        self._emit(LogCategory.SEARCH, message, level, fields)

    def index(self, message: str, *, level: str = "INFO", **fields: Any) -> None:
        self._emit(LogCategory.INDEX, message, level, fields)

    def mcp(self, message: str, *, level: str = "INFO", **fields: Any) -> None:
        self._emit(LogCategory.MCP, message, level, fields)

    def cache(self, message: str, *, level: str = "INFO", **fields: Any) -> None:
        self._emit(LogCategory.CACHE, message, level, fields)

    def infra(self, message: str, *, level: str = "INFO", **fields: Any) -> None:
        self._emit(LogCategory.INFRA, message, level, fields)

    def system(self, message: str, *, level: str = "INFO", **fields: Any) -> None:
        self._emit(LogCategory.SYSTEM, message, level, fields)

    def deps(self, message: str, *, level: str = "INFO", **fields: Any) -> None:
        self._emit(LogCategory.DEPS, message, level, fields)


# Module-level singleton — buffer resolved lazily via get_log_buffer()
_cs_log = CsLog()

# Convenience alias for: from cocosearch.logging import cs_log
cs_log = _cs_log
