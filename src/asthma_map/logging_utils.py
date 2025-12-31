"""
JSONL structured logging utilities.

Every script run creates a unique log file with structured entries
for full pipeline traceability.
"""
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from asthma_map.paths import LOGS_DIR


def generate_run_id() -> str:
    """Generate unique run ID: YYYYMMDD_HHMMSS_<8-char-uuid>"""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    short_uuid = uuid.uuid4().hex[:8]
    return f"{timestamp}_{short_uuid}"


class JSONLHandler(logging.Handler):
    """Logging handler that writes structured JSON lines to a file."""

    def __init__(self, log_path: Path, run_id: str):
        super().__init__()
        self.log_path = log_path
        self.run_id = run_id
        self._file = None

    def _ensure_file(self):
        if self._file is None:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._file = open(self.log_path, "a", encoding="utf-8")

    def emit(self, record: logging.LogRecord):
        try:
            self._ensure_file()

            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "run_id": self.run_id,
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }

            # Add structured fields if present
            if hasattr(record, "event_type"):
                log_entry["event_type"] = record.event_type
            if hasattr(record, "context"):
                log_entry["context"] = record.context

            self._file.write(json.dumps(log_entry, default=str) + "\n")
            self._file.flush()
        except Exception:
            self.handleError(record)

    def close(self):
        if self._file:
            self._file.close()
        super().close()


# Global run ID (set once per script execution)
_RUN_ID: str | None = None


def get_run_id() -> str:
    global _RUN_ID
    if _RUN_ID is None:
        _RUN_ID = generate_run_id()
    return _RUN_ID


def get_logger(script_name: str) -> logging.Logger:
    """
    Get or create a logger for a pipeline script.

    Creates both console and JSONL file handlers.
    """
    run_id = get_run_id()
    logger = logging.getLogger(f"{script_name}_{run_id}")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        # Console handler
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
        )
        logger.addHandler(console)

        # JSONL file handler
        log_file = LOGS_DIR / f"{script_name}_{run_id}.jsonl"
        jsonl_handler = JSONLHandler(log_file, run_id)
        jsonl_handler.setLevel(logging.DEBUG)
        logger.addHandler(jsonl_handler)

    return logger


def log_step_start(logger: logging.Logger, step_name: str, **context: Any) -> None:
    """Log the start of a processing step."""
    logger.info(
        f"Starting: {step_name}",
        extra={"event_type": "step_start", "context": {"step_name": step_name, **context}},
    )


def log_step_end(logger: logging.Logger, step_name: str, **context: Any) -> None:
    """Log the completion of a processing step."""
    logger.info(
        f"Completed: {step_name}",
        extra={"event_type": "step_end", "context": {"step_name": step_name, **context}},
    )


def log_output_written(
    logger: logging.Logger, path: Path, row_count: int | None = None, **context: Any
) -> None:
    """Log that an output file was written."""
    msg = f"Output written: {path}"
    if row_count:
        msg += f" ({row_count:,} rows)"
    logger.info(
        msg,
        extra={"event_type": "output_written", "context": {"path": str(path), "row_count": row_count, **context}},
    )


def log_qa_check(
    logger: logging.Logger, check_name: str, passed: bool, details: str | None = None
) -> None:
    """Log a QA check result."""
    status = "PASSED" if passed else "FAILED"
    level = logging.INFO if passed else logging.ERROR
    msg = f"QA Check [{check_name}]: {status}"
    if details:
        msg += f" - {details}"
    logger.log(
        level,
        msg,
        extra={"event_type": "qa_check", "context": {"check_name": check_name, "passed": passed, "details": details}},
    )

