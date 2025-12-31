"""Tests for the logging_utils module."""
import json
import re


def test_generate_run_id_format():
    """Test that run IDs match expected format."""
    from asthma_map.logging_utils import generate_run_id

    run_id = generate_run_id()

    # Format: YYYYMMDD_HHMMSS_<8-char-hex>
    pattern = r"^\d{8}_\d{6}_[a-f0-9]{8}$"
    assert re.match(pattern, run_id), f"Run ID '{run_id}' doesn't match expected format"


def test_generate_run_id_unique():
    """Test that run IDs are unique."""
    from asthma_map.logging_utils import generate_run_id

    ids = [generate_run_id() for _ in range(100)]
    assert len(set(ids)) == 100, "Generated duplicate run IDs"


def test_get_logger_creates_logger():
    """Test that get_logger creates a working logger."""
    from asthma_map.logging_utils import get_logger

    logger = get_logger("test_script")

    assert logger is not None
    assert len(logger.handlers) >= 1  # At least console handler


def test_log_step_functions_dont_raise():
    """Test that logging functions don't raise exceptions."""
    from asthma_map.logging_utils import (
        get_logger,
        log_step_start,
        log_step_end,
        log_output_written,
        log_qa_check,
    )
    from pathlib import Path

    logger = get_logger("test_script_functions")

    # These should all complete without raising
    log_step_start(logger, "test_step", extra_info="test")
    log_step_end(logger, "test_step", records_processed=100)
    log_output_written(logger, Path("/tmp/test.csv"), row_count=50)
    log_qa_check(logger, "test_check", passed=True, details="All good")
    log_qa_check(logger, "test_check_fail", passed=False, details="Something wrong")

