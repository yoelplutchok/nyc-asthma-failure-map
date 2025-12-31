#!/usr/bin/env python3
"""
Script 03: Fetch and Process Child Population Data from Census

Input:  Census API
Output: data/processed/child_population_by_uhf.csv

This script:
1. Queries the Census ACS 5-Year API for population by age by tract
2. Calculates total child population (ages 0-17) per tract
3. Aggregates tracts to UHF 42 neighborhoods using spatial join

Census Table B01001 (Sex by Age) columns for ages 0-17:
  Male: B01001_003E through B01001_006E (Under 5, 5-9, 10-14, 15-17)
  Female: B01001_027E through B01001_030E (Under 5, 5-9, 10-14, 15-17)
"""
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
import yaml

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


# Census API key - hardcoded for this project
CENSUS_API_KEY = "f526c41c700d725e285cfb5e985609ccabddabfd"


def load_params() -> dict:
    """Load parameters from configs/params.yml."""
    with open(CONFIGS_DIR / "params.yml") as f:
        return yaml.safe_load(f)


def fetch_census_population(state_fips: str, county_fips: str, year: int = 2022) -> pd.DataFrame:
    """
    Fetch population by age from Census ACS 5-Year API for a county.
    
    Returns DataFrame with tract-level child population.
    """
    # B01001 columns for ages 0-17
    # Male: 003=Under 5, 004=5-9, 005=10-14, 006=15-17
    # Female: 027=Under 5, 028=5-9, 029=10-14, 030=15-17
    variables = [
        "B01001_003E",  # Male Under 5
        "B01001_004E",  # Male 5-9
        "B01001_005E",  # Male 10-14
        "B01001_006E",  # Male 15-17
        "B01001_027E",  # Female Under 5
        "B01001_028E",  # Female 5-9
        "B01001_029E",  # Female 10-14
        "B01001_030E",  # Female 15-17
    ]
    
    base_url = f"https://api.census.gov/data/{year}/acs/acs5"
    params = {
        "get": ",".join(["NAME"] + variables),
        "for": "tract:*",
        "in": f"state:{state_fips} county:{county_fips}",
        "key": CENSUS_API_KEY,
    }
    
    response = requests.get(base_url, params=params, timeout=60)
    response.raise_for_status()
    
    data = response.json()
    headers = data[0]
    rows = data[1:]
    
    df = pd.DataFrame(rows, columns=headers)
    
    # Convert population columns to numeric
    for col in variables:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    
    # Calculate total child population (0-17)
    df["child_population"] = df[variables].sum(axis=1)
    
    # Create tract GEOID (state + county + tract)
    df["tract_geoid"] = df["state"] + df["county"] + df["tract"]
    
    return df[["tract_geoid", "NAME", "child_population"]]


def create_tract_centroids(uhf_boundaries: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    We need to assign tracts to UHF neighborhoods.
    Since we don't have tract boundaries, we'll use the Census Geocoder 
    to get tract locations, or use a tract-to-UHF crosswalk.
    
    For now, we'll fetch tract boundaries from Census TIGER/Line.
    """
    # This is a placeholder - we'll use a different approach below
    pass


def fetch_tract_boundaries(state_fips: str, county_fips: str, year: int = 2022) -> gpd.GeoDataFrame:
    """
    Fetch census tract boundaries from Census Cartographic Boundary files.
    
    Uses the cb_YEAR_STATE_tract_500k shapefiles.
    """
    # Census Cartographic Boundary files for tracts
    # Format: https://www2.census.gov/geo/tiger/GENZ{year}/shp/cb_{year}_{state}_tract_500k.zip
    url = f"https://www2.census.gov/geo/tiger/GENZ{year}/shp/cb_{year}_{state_fips}_tract_500k.zip"
    
    try:
        gdf = gpd.read_file(url)
        # Filter to the specific county
        gdf = gdf[gdf["COUNTYFP"] == county_fips].copy()
        return gdf
    except Exception as e:
        raise RuntimeError(f"Failed to fetch tract boundaries: {e}")


def main():
    """Main entry point."""
    logger = get_logger("03_process_population")
    run_id = get_run_id()

    log_step_start(logger, "fetch_census_population")

    # Load configuration
    params = load_params()
    census_config = params["census"]
    
    state_fips = census_config["state_fips"]
    year = census_config["year"]
    counties = census_config["nyc_counties"]

    # Fetch population data for each NYC county
    logger.info(f"Fetching Census population data for {len(counties)} NYC counties (year {year})")
    
    all_population_data = []
    for county_name, county_fips in counties.items():
        logger.info(f"  Fetching {county_name} (county {county_fips})...")
        try:
            df = fetch_census_population(state_fips, county_fips, year)
            df["county_name"] = county_name
            all_population_data.append(df)
            logger.info(f"    Got {len(df)} tracts, {df['child_population'].sum():,} children")
        except Exception as e:
            logger.error(f"    Failed to fetch {county_name}: {e}")
    
    population_df = pd.concat(all_population_data, ignore_index=True)
    logger.info(f"Total: {len(population_df)} tracts, {population_df['child_population'].sum():,} children")
    
    log_step_end(logger, "fetch_census_population", 
                 total_tracts=len(population_df),
                 total_children=int(population_df["child_population"].sum()))

    # Fetch tract boundaries for spatial join
    log_step_start(logger, "fetch_tract_boundaries")
    
    all_tract_boundaries = []
    for county_name, county_fips in counties.items():
        logger.info(f"  Fetching tract boundaries for {county_name}...")
        try:
            gdf = fetch_tract_boundaries(state_fips, county_fips, year)
            all_tract_boundaries.append(gdf)
            logger.info(f"    Got {len(gdf)} tract geometries")
        except Exception as e:
            logger.error(f"    Failed to fetch boundaries for {county_name}: {e}")
    
    tracts_gdf = pd.concat(all_tract_boundaries, ignore_index=True)
    tracts_gdf = gpd.GeoDataFrame(tracts_gdf, geometry="geometry")
    # Ensure consistent CRS (the cartographic files come in NAD83)
    if tracts_gdf.crs is None:
        tracts_gdf = tracts_gdf.set_crs("EPSG:4269")  # NAD83
    tracts_gdf = tracts_gdf.to_crs("EPSG:4326")
    
    log_step_end(logger, "fetch_tract_boundaries", total_tracts=len(tracts_gdf))

    # Merge population data with tract geometries
    log_step_start(logger, "spatial_join_to_uhf")
    
    # Cartographic boundary files use GEOID column
    # Format: state(2) + county(3) + tract(6) = 11 chars
    tracts_gdf["tract_geoid"] = tracts_gdf["GEOID"].astype(str)
    
    # Ensure population tract_geoid is also string and properly formatted
    population_df["tract_geoid"] = population_df["tract_geoid"].astype(str)
    
    logger.info(f"Sample tract GEOIDs from boundaries: {tracts_gdf['tract_geoid'].head(3).tolist()}")
    logger.info(f"Sample tract GEOIDs from population: {population_df['tract_geoid'].head(3).tolist()}")
    
    tracts_with_pop = tracts_gdf.merge(population_df, on="tract_geoid", how="left")
    tracts_with_pop["child_population"] = tracts_with_pop["child_population"].fillna(0)
    
    # Load UHF boundaries
    uhf_path = GEO_DIR / "uhf42_boundaries.geojson"
    uhf_gdf = gpd.read_file(uhf_path)
    uhf_gdf = uhf_gdf[uhf_gdf["GEOCODE"] != 0]  # Remove citywide polygon
    
    logger.info(f"Loaded {len(uhf_gdf)} UHF neighborhoods")
    
    # Get tract centroids for point-in-polygon join
    # Project to NY State Plane for accurate centroids, then back to WGS84
    tracts_projected = tracts_with_pop.to_crs("EPSG:2263")
    tracts_with_pop["centroid"] = tracts_projected.geometry.centroid.to_crs("EPSG:4326")
    tract_points = tracts_with_pop.set_geometry("centroid")
    
    # Spatial join: assign each tract centroid to a UHF neighborhood
    joined = gpd.sjoin(tract_points, uhf_gdf[["GEOCODE", "GEONAME", "geometry"]], 
                       how="left", predicate="within")
    
    # Some tracts may not fall within any UHF (edge cases, water, etc.)
    unmatched = joined["GEOCODE"].isna().sum()
    if unmatched > 0:
        logger.warning(f"{unmatched} tracts could not be matched to UHF neighborhoods")
    
    log_step_end(logger, "spatial_join_to_uhf", matched=len(joined) - unmatched, unmatched=unmatched)

    # Aggregate child population by UHF
    log_step_start(logger, "aggregate_by_uhf")
    
    uhf_population = joined.groupby(["GEOCODE", "GEONAME"]).agg({
        "child_population": "sum",
        "tract_geoid": "count"  # Count of tracts per UHF
    }).reset_index()
    
    uhf_population.columns = ["uhf_code", "uhf_name", "child_population", "tract_count"]
    uhf_population["child_population"] = uhf_population["child_population"].astype(int)
    
    logger.info(f"Aggregated to {len(uhf_population)} UHF neighborhoods")
    logger.info(f"Total child population: {uhf_population['child_population'].sum():,}")
    
    log_step_end(logger, "aggregate_by_uhf", uhf_count=len(uhf_population))

    # QA checks
    log_qa_check(
        logger,
        "all_uhf_have_population",
        passed=len(uhf_population) == 42,
        details=f"Got {len(uhf_population)} UHF neighborhoods (expected 42)"
    )
    
    min_pop = uhf_population["child_population"].min()
    log_qa_check(
        logger,
        "minimum_population_threshold",
        passed=min_pop >= 100,
        details=f"Minimum child population: {min_pop:,}"
    )

    # Write output
    output_path = PROCESSED_DIR / "child_population_by_uhf.csv"
    atomic_write_csv(output_path, uhf_population)
    log_output_written(logger, output_path, row_count=len(uhf_population))

    # Write metadata sidecar
    write_metadata_sidecar(
        data_path=output_path,
        script_name="03_process_population.py",
        run_id=run_id,
        description="Child population (ages 0-17) by UHF 42 neighborhood",
        inputs=[
            f"Census ACS 5-Year {year}",
            "Census TIGER/Line tract boundaries",
            str(uhf_path),
        ],
        row_count=len(uhf_population),
        columns=list(uhf_population.columns),
        census_year=year,
        total_child_population=int(uhf_population["child_population"].sum()),
        total_tracts=len(population_df),
    )

    logger.info(f"✓ Completed: Wrote child population for {len(uhf_population)} UHF neighborhoods")


if __name__ == "__main__":
    main()

