import logging
import os
import sys

from pythonjsonlogger import jsonlogger


def setup_json_logging(level: str | int | None = None, app_name: str = "finto") -> None:
    """Configure root logging to emit one-line JSON to stdout using python-json-logger.

    Safe to call multiple times; it will not duplicate handlers.
    """
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO")

    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers if already configured
    if any(
        isinstance(h, logging.StreamHandler)
        and isinstance(getattr(h, "formatter", None), jsonlogger.JsonFormatter)
        for h in root.handlers
    ):
        return

    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(module)s %(funcName)s %(lineno)d %(message)s",
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
            "name": "logger",
            "funcName": "func",
            "lineno": "line",
        },
        static_fields={"app": app_name},
    )
    handler.setFormatter(formatter)

    root.handlers.clear()
    root.addHandler(handler)

    # Make common third-party loggers inherit the same handler
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "httpx"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True


def logger_for(name: str) -> logging.Logger:
    """Convenience helper to get a module logger."""
    return logging.getLogger(name)
