"""Pytest configuration and shared fixtures."""
import pytest
from pathlib import Path


@pytest.fixture
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def sample_provider():
    """Return a sample provider record for testing."""
    return {
        "npi": "1234567890",
        "name": "Test Provider",
        "first_name": "Jane",
        "last_name": "Smith",
        "credential": "MD",
        "address": "123 Main St, New York, NY 10001",
        "city": "NEW YORK",
        "state": "NY",
        "zip": "10001",
        "specialty": "Pediatric Pulmonology",
        "taxonomy_code": "2080P0301X",
    }


@pytest.fixture
def sample_address():
    """Return a sample address for geocoding tests."""
    return "123 Main Street, New York, NY 10001"


@pytest.fixture
def sample_coordinates():
    """Return sample NYC coordinates (Times Square area)."""
    return {"lat": 40.7580, "lon": -73.9855}

