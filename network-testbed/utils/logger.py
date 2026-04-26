"""
utils/logger.py
Centralized structured logger with color output and file rotation.
"""

import logging
import logging.handlers
import os
import sys
from typing import Optional

LOG_DIR = os.environ.get("LOG_DIR", "logs")
LOG_FILE = os.path.join(LOG_DIR, "testbed.log")

# ANSI color codes
COLORS = {
    "DEBUG": "\033[36m",     # cyan
    "INFO": "\033[32m",      # green
    "WARNING": "\033[33m",   # yellow
    "ERROR": "\033[31m",     # red
    "CRITICAL": "\033[35m",  # magenta
    "RESET": "\033[0m",
}


class ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        color = COLORS.get(record.levelname, COLORS["RESET"])
        reset = COLORS["RESET"]
        record.levelname = f"{color}{record.levelname:8s}{reset}"
        return super().format(record)


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Already configured

    log_level = getattr(logging, (level or os.environ.get("LOG_LEVEL", "INFO")).upper(), logging.INFO)
    logger.setLevel(log_level)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(log_level)
    fmt = ColorFormatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
        datefmt="%H:%M:%S",
    )
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler (rotating)
    os.makedirs(LOG_DIR, exist_ok=True)
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(fh)

    return logger
