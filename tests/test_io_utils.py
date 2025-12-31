"""Tests for the io_utils module."""
import json
from pathlib import Path


def test_atomic_write_json_creates_file(tmp_path):
    """Test that atomic_write_json creates a valid JSON file."""
    from asthma_map.io_utils import atomic_write_json

    output_path = tmp_path / "test.json"
    data = {"key": "value", "number": 42}

    result = atomic_write_json(output_path, data)

    assert result == output_path
    assert output_path.exists()

    with open(output_path) as f:
        loaded = json.load(f)
    assert loaded == data


def test_atomic_write_json_no_tmp_on_success(tmp_path):
    """Test that no .tmp files remain after successful write."""
    from asthma_map.io_utils import atomic_write_json

    output_path = tmp_path / "test.json"
    atomic_write_json(output_path, {"test": True})

    tmp_files = list(tmp_path.glob("*.tmp"))
    assert len(tmp_files) == 0, f"Found leftover tmp files: {tmp_files}"


def test_write_metadata_sidecar(tmp_path):
    """Test that metadata sidecar is created correctly."""
    from asthma_map.io_utils import write_metadata_sidecar

    data_path = tmp_path / "test_data.csv"
    data_path.touch()  # Create empty file

    meta_path = write_metadata_sidecar(
        data_path=data_path,
        script_name="test_script.py",
        run_id="20241230_120000_abc12345",
        description="Test data file",
        inputs=["input1.csv", "input2.csv"],
        row_count=100,
        columns=["col1", "col2", "col3"],
    )

    expected_meta_path = tmp_path / "test_data_metadata.json"
    assert meta_path == expected_meta_path
    assert meta_path.exists()

    with open(meta_path) as f:
        metadata = json.load(f)

    assert metadata["_script"] == "test_script.py"
    assert metadata["_run_id"] == "20241230_120000_abc12345"
    assert metadata["description"] == "Test data file"
    assert metadata["inputs"] == ["input1.csv", "input2.csv"]
    assert metadata["row_count"] == 100
    assert metadata["columns"] == ["col1", "col2", "col3"]
    assert "_generated" in metadata
    assert "_version" in metadata


def test_clean_tmp_files(tmp_path):
    """Test that clean_tmp_files removes .tmp files."""
    from asthma_map.io_utils import clean_tmp_files

    # Create some .tmp files
    (tmp_path / "file1.tmp").touch()
    (tmp_path / "file2.tmp").touch()
    (tmp_path / "file3.json").touch()  # Should not be removed

    removed = clean_tmp_files(tmp_path)

    assert len(removed) == 2
    assert not (tmp_path / "file1.tmp").exists()
    assert not (tmp_path / "file2.tmp").exists()
    assert (tmp_path / "file3.json").exists()

