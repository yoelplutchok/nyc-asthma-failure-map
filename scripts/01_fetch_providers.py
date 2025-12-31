#!/usr/bin/env python3
"""
Script 01: Fetch Healthcare Providers from NPI Registry

Input:  None (fetches from CMS NPPES API)
Output: data/raw/npi_providers_raw.json

This script queries the CMS NPPES NPI Registry API to retrieve
all pediatric pulmonologists, allergists, and pediatricians practicing in NYC.

API Documentation: https://npiregistry.cms.hhs.gov/api-page
"""
import json
import time
from pathlib import Path

import requests
import yaml

from asthma_map.paths import RAW_DIR, CONFIGS_DIR
from asthma_map.io_utils import atomic_write_json, write_metadata_sidecar
from asthma_map.logging_utils import (
    get_logger,
    get_run_id,
    log_step_start,
    log_step_end,
    log_output_written,
    log_qa_check,
)


def load_params() -> dict:
    """Load parameters from configs/params.yml."""
    with open(CONFIGS_DIR / "params.yml") as f:
        return yaml.safe_load(f)


def fetch_npi_providers(
    taxonomy_description: str,
    city: str,
    state: str = "NY",
    limit: int = 200,
    delay: float = 0.1,
    logger=None,
) -> list[dict]:
    """
    Fetch providers from NPI Registry API for a given taxonomy description and city.

    The API returns max 200 results per query, so we paginate using 'skip'.
    Note: The API uses taxonomy_description for text search, not taxonomy codes.
    """
    base_url = "https://npiregistry.cms.hhs.gov/api/"
    all_results = []
    skip = 0

    while True:
        params = {
            "version": "2.1",
            "taxonomy_description": taxonomy_description,
            "city": city,
            "state": state,
            "limit": limit,
            "skip": skip,
        }

        try:
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            if logger:
                logger.warning(f"API request failed for {city}/{taxonomy_code}: {e}")
            break

        results = data.get("results", [])
        result_count = data.get("result_count", 0)

        if not results:
            break

        all_results.extend(results)

        if logger:
            logger.debug(f"Fetched {len(results)} providers from {city} (skip={skip})")

        # Check if we've gotten all results
        if len(all_results) >= result_count or len(results) < limit:
            break

        skip += limit
        time.sleep(delay)  # Rate limiting

    return all_results


def extract_provider_info(npi_record: dict) -> dict | None:
    """
    Extract relevant fields from an NPI record.

    Returns None if the record doesn't have required fields.
    """
    try:
        basic = npi_record.get("basic", {})
        addresses = npi_record.get("addresses", [])
        taxonomies = npi_record.get("taxonomies", [])

        # Find practice location address (not mailing)
        practice_address = None
        for addr in addresses:
            if addr.get("address_purpose") == "LOCATION":
                practice_address = addr
                break

        # Fall back to first address if no LOCATION found
        if not practice_address and addresses:
            practice_address = addresses[0]

        if not practice_address:
            return None

        # Get primary taxonomy
        primary_taxonomy = None
        for tax in taxonomies:
            if tax.get("primary", False):
                primary_taxonomy = tax
                break
        if not primary_taxonomy and taxonomies:
            primary_taxonomy = taxonomies[0]

        return {
            "npi": npi_record.get("number"),
            "entity_type": npi_record.get("enumeration_type"),
            "first_name": basic.get("first_name", ""),
            "last_name": basic.get("last_name", ""),
            "credential": basic.get("credential", ""),
            "organization_name": basic.get("organization_name", ""),
            "address_1": practice_address.get("address_1", ""),
            "address_2": practice_address.get("address_2", ""),
            "city": practice_address.get("city", ""),
            "state": practice_address.get("state", ""),
            "postal_code": practice_address.get("postal_code", "")[:5],  # First 5 digits
            "phone": practice_address.get("telephone_number", ""),
            "taxonomy_code": primary_taxonomy.get("code", "") if primary_taxonomy else "",
            "taxonomy_desc": primary_taxonomy.get("desc", "") if primary_taxonomy else "",
            "taxonomy_license": primary_taxonomy.get("license", "") if primary_taxonomy else "",
        }
    except Exception:
        return None


def main():
    """Main entry point."""
    logger = get_logger("01_fetch_providers")
    run_id = get_run_id()

    log_step_start(logger, "fetch_npi_providers")

    # Load configuration
    params = load_params()
    npi_config = params["npi_api"]

    taxonomy_descriptions = npi_config["taxonomy_descriptions"]
    taxonomy_codes = npi_config["taxonomy_codes"]  # For reference in output
    cities = npi_config["cities"]
    delay = npi_config.get("rate_limit_delay", 0.1)

    logger.info(f"Fetching providers for {len(taxonomy_descriptions)} specialties in {len(cities)} cities")

    # Fetch all providers
    all_raw_results = []
    fetch_stats = {}

    for specialty_name, taxonomy_desc in taxonomy_descriptions.items():
        logger.info(f"Fetching {specialty_name} ({taxonomy_desc})...")
        specialty_count = 0

        for city in cities:
            results = fetch_npi_providers(
                taxonomy_description=taxonomy_desc,
                city=city,
                delay=delay,
                logger=logger,
            )
            all_raw_results.extend(results)
            specialty_count += len(results)
            logger.debug(f"  {city}: {len(results)} providers")
            time.sleep(delay)

        fetch_stats[specialty_name] = specialty_count
        logger.info(f"  Total {specialty_name}: {specialty_count}")

    logger.info(f"Total raw results: {len(all_raw_results)}")

    # Extract and clean provider info
    log_step_start(logger, "extract_provider_info")
    providers = []
    seen_npis = set()

    for record in all_raw_results:
        provider = extract_provider_info(record)
        if provider and provider["npi"] and provider["npi"] not in seen_npis:
            providers.append(provider)
            seen_npis.add(provider["npi"])

    logger.info(f"Unique providers after deduplication: {len(providers)}")
    log_step_end(logger, "extract_provider_info", unique_count=len(providers))

    # QA checks
    log_qa_check(
        logger,
        "minimum_providers",
        passed=len(providers) >= 100,
        details=f"Found {len(providers)} providers (expected >= 100)",
    )

    nyc_states = [p for p in providers if p["state"] == "NY"]
    log_qa_check(
        logger,
        "all_ny_state",
        passed=len(nyc_states) == len(providers),
        details=f"{len(nyc_states)}/{len(providers)} providers in NY state",
    )

    # Write output
    output_path = RAW_DIR / "npi_providers_raw.json"
    atomic_write_json(output_path, providers)
    log_output_written(logger, output_path, row_count=len(providers))

    # Write metadata sidecar
    write_metadata_sidecar(
        data_path=output_path,
        script_name="01_fetch_providers.py",
        run_id=run_id,
        description="Raw provider data from CMS NPPES NPI Registry API",
        inputs=[],
        row_count=len(providers),
        columns=list(providers[0].keys()) if providers else [],
        fetch_stats=fetch_stats,
        api_source="https://npiregistry.cms.hhs.gov/api/",
        taxonomy_codes=taxonomy_codes,
        cities_queried=cities,
    )

    log_step_end(
        logger,
        "fetch_npi_providers",
        total_providers=len(providers),
        fetch_stats=fetch_stats,
    )

    logger.info(f"✓ Completed: Wrote {len(providers)} providers to {output_path}")


if __name__ == "__main__":
    main()

