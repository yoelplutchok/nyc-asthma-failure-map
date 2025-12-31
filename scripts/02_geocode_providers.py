#!/usr/bin/env python3
"""
Script 02: Geocode Provider Addresses

Input:  data/raw/npi_providers_raw.json
Output: data/processed/providers_geocoded.csv

This script:
1. Loads provider data from the NPI fetch
2. Geocodes each address using the Census Geocoder API
3. Assigns each provider to a UHF neighborhood via spatial join
4. Outputs geocoded providers with lat/lon and UHF assignment
"""
import json
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
import yaml
from shapely.geometry import Point

from asthma_map.paths import RAW_DIR, PROCESSED_DIR, GEO_DIR, CONFIGS_DIR
from asthma_map.io_utils import atomic_write_csv, write_metadata_sidecar
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


def clean_address(address_1: str, address_2: str, city: str, state: str, zip_code: str) -> str:
    """
    Clean and format address for geocoding.
    
    Removes suite numbers, floor numbers, and other elements that confuse geocoders.
    """
    # Start with address_1
    addr = str(address_1).strip() if address_1 else ""
    
    # Remove common suite/floor patterns
    import re
    patterns_to_remove = [
        r'\bSTE\.?\s*\d+\w*',
        r'\bSUITE\s*\d+\w*',
        r'\bFL\.?\s*\d+',
        r'\bFLOOR\s*\d+',
        r'\bAPT\.?\s*\d+\w*',
        r'\bROOM\s*\d+\w*',
        r'\bRM\.?\s*\d+\w*',
        r'\b#\s*\d+\w*',
        r'\bUNIT\s*\d+\w*',
    ]
    
    for pattern in patterns_to_remove:
        addr = re.sub(pattern, '', addr, flags=re.IGNORECASE)
    
    # Clean up extra spaces and commas
    addr = re.sub(r'\s+', ' ', addr).strip()
    addr = re.sub(r',\s*,', ',', addr)
    
    # Build full address
    full_address = f"{addr}, {city}, {state} {zip_code}"
    return full_address


def geocode_address(address: str, timeout: int = 30) -> dict | None:
    """
    Geocode an address using the Census Geocoder API.
    
    Returns dict with lat, lon, tract or None if geocoding fails.
    """
    base_url = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
    
    params = {
        "address": address,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "format": "json",
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        
        matches = data.get("result", {}).get("addressMatches", [])
        if not matches:
            return None
        
        match = matches[0]
        coords = match.get("coordinates", {})
        geographies = match.get("geographies", {})
        
        # Get census tract info
        tracts = geographies.get("Census Tracts", [{}])
        tract_info = tracts[0] if tracts else {}
        
        return {
            "lat": coords.get("y"),
            "lon": coords.get("x"),
            "matched_address": match.get("matchedAddress", ""),
            "tract_geoid": tract_info.get("GEOID", ""),
        }
    except Exception:
        return None


def main():
    """Main entry point."""
    logger = get_logger("02_geocode_providers")
    run_id = get_run_id()

    # Load configuration
    params = load_params()
    delay = params["npi_api"].get("rate_limit_delay", 0.1)

    # Load provider data
    log_step_start(logger, "load_providers")
    
    input_path = RAW_DIR / "npi_providers_raw.json"
    with open(input_path) as f:
        providers = json.load(f)
    
    logger.info(f"Loaded {len(providers)} providers from {input_path}")
    log_step_end(logger, "load_providers", count=len(providers))

    # Filter to NY state only (some NJ providers may have slipped in)
    providers = [p for p in providers if p.get("state") == "NY"]
    logger.info(f"Filtered to {len(providers)} NY state providers")

    # Geocode each provider
    log_step_start(logger, "geocode_addresses")
    
    geocoded_results = []
    success_count = 0
    fail_count = 0
    
    for i, provider in enumerate(providers):
        # Build clean address
        address = clean_address(
            provider.get("address_1", ""),
            provider.get("address_2", ""),
            provider.get("city", ""),
            provider.get("state", ""),
            provider.get("postal_code", ""),
        )
        
        # Geocode
        result = geocode_address(address)
        
        # Build output record
        record = {
            "npi": provider.get("npi"),
            "first_name": provider.get("first_name"),
            "last_name": provider.get("last_name"),
            "credential": provider.get("credential"),
            "organization_name": provider.get("organization_name"),
            "taxonomy_code": provider.get("taxonomy_code"),
            "taxonomy_desc": provider.get("taxonomy_desc"),
            "address_original": f"{provider.get('address_1', '')}, {provider.get('city', '')}, {provider.get('state', '')} {provider.get('postal_code', '')}",
            "address_cleaned": address,
        }
        
        if result:
            record.update({
                "lat": result["lat"],
                "lon": result["lon"],
                "matched_address": result["matched_address"],
                "tract_geoid": result["tract_geoid"],
                "geocode_success": True,
            })
            success_count += 1
        else:
            record.update({
                "lat": None,
                "lon": None,
                "matched_address": None,
                "tract_geoid": None,
                "geocode_success": False,
            })
            fail_count += 1
        
        geocoded_results.append(record)
        
        # Progress logging
        if (i + 1) % 50 == 0:
            logger.info(f"  Geocoded {i + 1}/{len(providers)} ({success_count} success, {fail_count} failed)")
        
        time.sleep(delay)
    
    success_rate = success_count / len(providers) * 100 if providers else 0
    logger.info(f"Geocoding complete: {success_count}/{len(providers)} ({success_rate:.1f}% success)")
    log_step_end(logger, "geocode_addresses", 
                 success=success_count, failed=fail_count, rate=round(success_rate, 1))

    # Convert to DataFrame
    df = pd.DataFrame(geocoded_results)

    # Spatial join to UHF neighborhoods
    log_step_start(logger, "assign_uhf_neighborhoods")
    
    # Load UHF boundaries
    uhf_gdf = gpd.read_file(GEO_DIR / "uhf42_boundaries.geojson")
    uhf_gdf = uhf_gdf[uhf_gdf["GEOCODE"] != 0]  # Remove citywide polygon
    
    # Create points from geocoded providers
    geocoded_df = df[df["geocode_success"] == True].copy()
    geometry = [Point(lon, lat) for lon, lat in zip(geocoded_df["lon"], geocoded_df["lat"])]
    providers_gdf = gpd.GeoDataFrame(geocoded_df, geometry=geometry, crs="EPSG:4326")
    
    # Spatial join
    joined = gpd.sjoin(providers_gdf, uhf_gdf[["GEOCODE", "GEONAME", "geometry"]], 
                       how="left", predicate="within")
    
    # Merge UHF info back to full dataframe
    uhf_mapping = joined[["npi", "GEOCODE", "GEONAME"]].rename(
        columns={"GEOCODE": "uhf_code", "GEONAME": "uhf_name"}
    )
    df = df.merge(uhf_mapping, on="npi", how="left")
    
    # Count providers assigned to UHF
    assigned = df["uhf_code"].notna().sum()
    logger.info(f"Assigned {assigned}/{len(df)} providers to UHF neighborhoods")
    log_step_end(logger, "assign_uhf_neighborhoods", assigned=int(assigned))

    # QA checks
    log_qa_check(
        logger,
        "geocode_success_rate",
        passed=success_rate >= 85,
        details=f"Geocoded {success_rate:.1f}% of addresses (target >= 85%)"
    )
    
    uhf_coverage = assigned / len(df) * 100 if len(df) > 0 else 0
    log_qa_check(
        logger,
        "uhf_assignment_rate",
        passed=uhf_coverage >= 80,
        details=f"Assigned {uhf_coverage:.1f}% to UHF neighborhoods (target >= 80%)"
    )

    # Write output
    output_path = PROCESSED_DIR / "providers_geocoded.csv"
    atomic_write_csv(output_path, df)
    log_output_written(logger, output_path, row_count=len(df))

    # Write metadata sidecar
    write_metadata_sidecar(
        data_path=output_path,
        script_name="02_geocode_providers.py",
        run_id=run_id,
        description="Geocoded provider addresses with UHF neighborhood assignment",
        inputs=[str(input_path)],
        row_count=len(df),
        columns=list(df.columns),
        geocoding={
            "api": "Census Geocoder",
            "success_count": success_count,
            "fail_count": fail_count,
            "success_rate": round(success_rate, 2),
        },
        uhf_assignment={
            "assigned_count": int(assigned),
            "coverage_rate": round(uhf_coverage, 2),
        },
    )

    logger.info(f"✓ Completed: Geocoded {len(df)} providers, {int(assigned)} assigned to UHF")


if __name__ == "__main__":
    main()

