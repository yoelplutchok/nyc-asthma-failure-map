"""Tests for the paths module."""
from pathlib import Path


def test_paths_exist(project_root):
    """Test that required directories exist."""
    from asthma_map.paths import RAW_DIR, PROCESSED_DIR, GEO_DIR, FINAL_DIR, LOGS_DIR

    assert RAW_DIR.exists(), f"RAW_DIR does not exist: {RAW_DIR}"
    assert PROCESSED_DIR.exists(), f"PROCESSED_DIR does not exist: {PROCESSED_DIR}"
    assert GEO_DIR.exists(), f"GEO_DIR does not exist: {GEO_DIR}"
    assert FINAL_DIR.exists(), f"FINAL_DIR does not exist: {FINAL_DIR}"
    assert LOGS_DIR.exists(), f"LOGS_DIR does not exist: {LOGS_DIR}"


def test_project_root_is_correct(project_root):
    """Test that PROJECT_ROOT points to the correct directory."""
    from asthma_map.paths import PROJECT_ROOT

    # PROJECT_ROOT should contain key files/directories
    assert (PROJECT_ROOT / "pyproject.toml").exists()
    assert (PROJECT_ROOT / "src").exists()
    assert (PROJECT_ROOT / "data").exists()


def test_ensure_dir_creates_directory(tmp_path):
    """Test that ensure_dir creates directories."""
    from asthma_map.paths import ensure_dir

    new_dir = tmp_path / "new" / "nested" / "directory"
    assert not new_dir.exists()

    result = ensure_dir(new_dir)

    assert new_dir.exists()
    assert result == new_dir

