# NYC Asthma Failure Map - Makefile
#
# Usage:
#   make all       - Run full pipeline
#   make data      - Run data processing only
#   make web       - Build web assets only
#   make clean     - Remove generated files
#   make test      - Run tests

.PHONY: all data web clean test help

PYTHON := python
SCRIPTS := scripts

help:
	@echo "NYC Asthma Failure Map - Commands"
	@echo ""
	@echo "  make all       Run full pipeline"
	@echo "  make data      Run data processing (scripts 01-05)"
	@echo "  make web       Build web visualization (script 06)"
	@echo "  make test      Run test suite"
	@echo "  make clean     Remove generated outputs"
	@echo "  make lint      Run linters (black, ruff)"
	@echo "  make format    Auto-format code with black"

# Individual steps with dependencies
01-fetch:
	$(PYTHON) $(SCRIPTS)/01_fetch_providers.py

02-geocode: 01-fetch
	$(PYTHON) $(SCRIPTS)/02_geocode_providers.py

03-population:
	$(PYTHON) $(SCRIPTS)/03_process_population.py

04-merge: 02-geocode 03-population
	$(PYTHON) $(SCRIPTS)/04_merge_datasets.py

05-classify: 04-merge
	$(PYTHON) $(SCRIPTS)/05_calculate_classes.py

06-export: 05-classify
	$(PYTHON) $(SCRIPTS)/06_export_for_web.py

# Aggregate targets
data: 05-classify
	@echo "Data processing complete"

web: 06-export
	@echo "Web assets ready"

all: web
	@echo "Full pipeline complete"

test:
	pytest tests/ -v

lint:
	ruff check src/ scripts/ tests/
	black --check src/ scripts/ tests/

format:
	black src/ scripts/ tests/
	ruff check --fix src/ scripts/ tests/

clean:
	rm -rf data/processed/*
	rm -rf data/final/*
	rm -rf web/data/*
	rm -rf logs/*.log
	rm -rf logs/*.jsonl
	@echo "Cleaned generated outputs (kept raw data and geo boundaries)"

# Keep .gitkeep files
clean-all: clean
	find data -name ".gitkeep" -delete
	@echo "Cleaned all including .gitkeep files"

