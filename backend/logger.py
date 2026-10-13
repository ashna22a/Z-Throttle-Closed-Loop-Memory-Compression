"""Structured logging setup."""

import logging
import sys


_configured = False


def _configure(log_path: str) -> None:
    global _configured
    if _configured:
        return

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    formatter = logging.Formatter(fmt)

    # Console
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    # File (best-effort; may fail without root)
    handlers = [console]
    try:
        fh = logging.FileHandler(log_path)
        fh.setFormatter(formatter)
        handlers.append(fh)
    except (PermissionError, FileNotFoundError):
        pass

    logging.basicConfig(level=logging.INFO, handlers=handlers)
    _configured = True


def get_logger(name: str, log_path: str = "/var/log/z-throttle.log"):
    _configure(log_path)
    return logging.getLogger(name)
