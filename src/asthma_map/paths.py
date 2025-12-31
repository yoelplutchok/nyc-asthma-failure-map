"""Centralized path management for the asthma map project."""
from pathlib import Path

# Project root (two levels up from this file)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Data directories
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
GEO_DIR = DATA_DIR / "geo"
FINAL_DIR = DATA_DIR / "final"

# Other directories
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
CONFIGS_DIR = PROJECT_ROOT / "configs"
WEB_DIR = PROJECT_ROOT / "web"
LOGS_DIR = PROJECT_ROOT / "logs"
AUDIT_DIR = PROJECT_ROOT / "audit"


def ensure_dir(path: Path) -> Path:
    """Ensure a directory exists, creating it if necessary."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


# Ensure directories exist on import
for d in [RAW_DIR, PROCESSED_DIR, GEO_DIR, FINAL_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

