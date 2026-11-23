import contextvars
import json
import logging
import sys
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Literal

run_id_ctx_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("run_id", default=None)


@contextmanager
def bind_run_id(run_id: str | None) -> Generator[None]:
    token = run_id_ctx_var.set(run_id)
    try:
        yield
    finally:
        run_id_ctx_var.reset(token)


class RunIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = run_id_ctx_var.get() or "-"
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, str] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "run_id": str(getattr(record, "run_id", "-")),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(
    level: str = "INFO",
    log_format: Literal["console", "json"] = "console",
) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RunIdFilter())
    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | run=%(run_id)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level.upper())

    for noisy_logger in ("httpx", "httpcore", "sqlalchemy.engine"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
