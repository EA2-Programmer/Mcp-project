"""
Logging configuration for the TrakSYS MCP Server.

All logging goes to stderr. stdout is reserved for MCP JSON-RPC
communication — anything written there corrupts the protocol stream.
"""

import json
import logging
import re
import sys

from src.traksys_mcp.config.setting import settings


class SensitiveDataFilter(logging.Filter):
    """
    Redacts credentials from log messages before they are written.

    Targets the PWD= field in ODBC connection strings, which is the
    most likely place a password appears in a log line.
    """

    # Matches PWD=<anything> up to the next semicolon or end of string
    _PWD_PATTERN = re.compile(r"(PWD=)[^;]+", re.IGNORECASE)

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._PWD_PATTERN.sub(r"\1***", record.msg)
        return True


class JSONFormatter(logging.Formatter):
    """Formats log records as structured JSON for production use."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging() -> None:
    """
    Configure root logger for the MCP server.

    Must be called once at server startup before any other module
    imports logging. Subsequent calls are safe — existing handlers
    are cleared first.
    """
    log_level_name = settings.LOG_LEVEL.upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    if log_level is None:
        # Fallback to stderr since logger not fully configured yet
        print(f"WARNING: Invalid LOG_LEVEL '{settings.LOG_LEVEL}', using INFO", file=sys.stderr)
        log_level = logging.INFO

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear any handlers added before setup_logging() was called
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # stderr ONLY — stdout belongs to the MCP protocol
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(log_level)
    handler.addFilter(SensitiveDataFilter())

    if settings.LOG_FORMAT == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))

    root_logger.addHandler(handler)

    # Silence libraries that log at DEBUG/INFO by default
    logging.getLogger("pyodbc").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logging.info("Logging ready — level=%s format=%s", settings.LOG_LEVEL, settings.LOG_FORMAT)