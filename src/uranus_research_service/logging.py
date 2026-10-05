"""Only fixed event names and reviewed operational fields can reach JSON logs."""

import json
import logging

FIELDS = {
    "request_id",
    "status_code",
    "duration_ms",
    "dependency",
    "error_type",
    "contract_version",
}
EVENTS = {"request_completed", "dependency_failed", "startup_failed"}
logger = logging.getLogger("uranus.research")


class SafeFormatter(logging.Formatter):
    def format(self, record):
        event = (
            record.msg if isinstance(record.msg, str) and record.msg in EVENTS else "internal_event"
        )
        return json.dumps(
            {"event": event, **{k: getattr(record, k) for k in FIELDS if hasattr(record, k)}},
            allow_nan=False,
        )


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(SafeFormatter())
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    # Provider transports and ASGI access/error logs may include URLs or exception values.
    for name in ("httpx", "httpcore", "uvicorn.access", "uvicorn.error"):
        logging.getLogger(name).disabled = True
