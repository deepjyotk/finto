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

    class ColoredFormatter(jsonlogger.JsonFormatter):
        COLORS = {
            "WARNING": "\033[95m",  # Pink
            "ERROR": "\033[91m",  # Red
            "CRITICAL": "\033[91m",  # Red
            "RESET": "\033[0m",
        }

        def format(self, record):
            log_message = super().format(record)
            if record.levelname in self.COLORS:
                return f"{self.COLORS[record.levelname]}{log_message}{self.COLORS['RESET']}"
            return log_message

    handler = logging.StreamHandler(sys.stdout)
    formatter = ColoredFormatter(
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

    # Add filter to upgrade log level for HTTP errors
    class HTTPErrorFilter(logging.Filter):
        def filter(self, record):
            msg = record.getMessage()
            parts = msg.split('" ')
            if len(parts) > 1:
                status_part = parts[1].split()[0]
                if status_part.startswith(("4", "5")):
                    record.levelno = logging.ERROR
                    record.levelname = "ERROR"
            return True

    logging.getLogger("uvicorn.access").addFilter(HTTPErrorFilter())


def logger_for(name: str) -> logging.Logger:
    """Convenience helper to get a module logger."""
    return logging.getLogger(name)
