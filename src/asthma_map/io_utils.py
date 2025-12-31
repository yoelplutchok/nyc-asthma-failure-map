"""
Atomic writes and I/O utilities.

Guardrail: Write to temp file → rename/replace.
Any .tmp files in data directories indicate failed writes.
"""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from asthma_map.paths import ensure_dir


def atomic_write(target_path: Path, write_func: Callable, *args: Any, **kwargs: Any) -> Path:
    """
    Write to a file atomically using temp file + rename.

    If write fails, target file is unchanged.
    """
    target_path = Path(target_path)
    ensure_dir(target_path.parent)

    # Create temp file in same directory (same filesystem for atomic rename)
    temp_fd, temp_path = tempfile.mkstemp(
        suffix=".tmp", prefix=f"{target_path.stem}_", dir=target_path.parent
    )
    temp_path = Path(temp_path)

    try:
        os.close(temp_fd)
        write_func(temp_path, *args, **kwargs)
        temp_path.replace(target_path)  # Atomic rename
        return target_path
    except Exception:
        if temp_path.exists():
            temp_path.unlink()  # Clean up on failure
        raise


def atomic_write_json(path: Path, data: Any, indent: int = 2) -> Path:
    """Write JSON atomically."""

    def _write(temp_path: Path, data: Any, indent: int) -> None:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, default=str)

    return atomic_write(path, _write, data, indent)


def atomic_write_csv(path: Path, df: Any, **kwargs: Any) -> Path:
    """Write DataFrame to CSV atomically."""

    def _write(temp_path: Path, df: Any, **kwargs: Any) -> None:
        df.to_csv(temp_path, index=False, **kwargs)

    return atomic_write(path, _write, df, **kwargs)


def atomic_write_geojson(path: Path, gdf: Any) -> Path:
    """Write GeoDataFrame to GeoJSON atomically."""

    def _write(temp_path: Path, gdf: Any) -> None:
        gdf.to_file(temp_path, driver="GeoJSON")

    return atomic_write(path, _write, gdf)


def clean_tmp_files(directory: Path) -> list[Path]:
    """Remove .tmp files (failed atomic writes) from a directory."""
    removed = []
    for tmp_file in Path(directory).glob("*.tmp"):
        tmp_file.unlink()
        removed.append(tmp_file)
    return removed


def write_metadata_sidecar(
    data_path: Path,
    script_name: str,
    run_id: str,
    description: str,
    inputs: list[str],
    row_count: int | None = None,
    columns: list[str] | None = None,
    **extra: Any,
) -> Path:
    """Write a metadata sidecar file for a data output."""
    meta_path = data_path.parent / f"{data_path.stem}_metadata.json"

    metadata: dict[str, Any] = {
        "_generated": datetime.now(timezone.utc).isoformat(),
        "_script": script_name,
        "_run_id": run_id,
        "_version": "0.1.0",
        "description": description,
        "inputs": inputs,
    }

    if row_count is not None:
        metadata["row_count"] = row_count
    if columns is not None:
        metadata["columns"] = columns

    metadata.update(extra)

    return atomic_write_json(meta_path, metadata)

