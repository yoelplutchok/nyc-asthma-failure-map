#!/usr/bin/env python3
"""
Script 04: Merge All Datasets

Inputs:
    - data/geo/uhf42_boundaries.geojson (base geography)
    - data/raw/asthma_er_visits_children_age 4 and under.csv
    - data/raw/asthma_er_visits_children_age 5 to 17.csv
    - data/processed/providers_geocoded.csv
    - data/processed/child_population_by_uhf.csv

Output:
    - data/processed/uhf_analysis_data.geojson

This script merges all data sources into a single analysis-ready dataset.
"""
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml

from asthma_map.paths import RAW_DIR, PROCESSED_DIR, GEO_DIR, CONFIGS_DIR
from asthma_map.io_utils import atomic_write_geojson, write_metadata_sidecar
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


def load_er_data() -> pd.DataFrame:
    """
    Load and combine asthma ER visit data for both age groups.
    
    Returns DataFrame with UHF-level rates.
    """
    # Load both age group files
    er_under5 = pd.read_csv(RAW_DIR / "asthma_er_visits_children_age 4 and under.csv")
    er_5to17 = pd.read_csv(RAW_DIR / "asthma_er_visits_children_age 5 to 17.csv")
    
    # Filter to UHF42 geography only and most recent year (2023)
    er_under5 = er_under5[(er_under5["GeoType"] == "UHF42") & (er_under5["TimePeriod"] == 2023)].copy()
    er_5to17 = er_5to17[(er_5to17["GeoType"] == "UHF42") & (er_5to17["TimePeriod"] == 2023)].copy()
    
    # Clean up column names and extract rate
    # The rate column has a long name with commas
    rate_col = "Estimated annual rate per 10,000"
    
    er_under5 = er_under5[["GeoID", "Geography", rate_col, "Number"]].rename(columns={
        "GeoID": "uhf_code",
        "Geography": "uhf_name",
        rate_col: "er_rate_under5",
        "Number": "er_count_under5",
    })
    
    er_5to17 = er_5to17[["GeoID", "Geography", rate_col, "Number"]].rename(columns={
        "GeoID": "uhf_code",
        "Geography": "uhf_name",
        rate_col: "er_rate_5to17",
        "Number": "er_count_5to17",
    })
    
    # Clean the rate columns (remove commas and asterisks from numbers)
    for df in [er_under5, er_5to17]:
        for col in df.columns:
            if "rate" in col or "count" in col:
                # Remove commas, asterisks, and other non-numeric chars (except decimal point)
                df[col] = df[col].astype(str).str.replace(",", "").str.replace("*", "").str.strip()
                df[col] = pd.to_numeric(df[col], errors="coerce")
    
    # Merge the two age groups
    er_data = er_under5.merge(er_5to17[["uhf_code", "er_rate_5to17", "er_count_5to17"]], 
                              on="uhf_code", how="outer")
    
    return er_data


def aggregate_providers(providers_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate provider counts by UHF neighborhood.
    """
    # Filter to successfully geocoded providers with UHF assignment
    valid = providers_df[providers_df["uhf_code"].notna()].copy()
    
    # Count by UHF
    provider_counts = valid.groupby("uhf_code").agg({
        "npi": "count",
        "taxonomy_desc": lambda x: x.value_counts().to_dict()
    }).reset_index()
    
    provider_counts.columns = ["uhf_code", "total_providers", "specialty_breakdown"]
    
    # Count specific specialties
    pulm_counts = valid[valid["taxonomy_desc"].str.contains("Pulmon", case=False, na=False)].groupby("uhf_code").size()
    allergy_counts = valid[valid["taxonomy_desc"].str.contains("Allergy|Immunology", case=False, na=False)].groupby("uhf_code").size()
    peds_counts = valid[valid["taxonomy_desc"].str.contains("Pediatric", case=False, na=False) & 
                        ~valid["taxonomy_desc"].str.contains("Pulmon", case=False, na=False)].groupby("uhf_code").size()
    
    provider_counts["pulmonology_count"] = provider_counts["uhf_code"].map(pulm_counts).fillna(0).astype(int)
    provider_counts["allergy_count"] = provider_counts["uhf_code"].map(allergy_counts).fillna(0).astype(int)
    provider_counts["pediatrics_count"] = provider_counts["uhf_code"].map(peds_counts).fillna(0).astype(int)
    
    # Drop the specialty_breakdown dict column (can't serialize to GeoJSON)
    provider_counts = provider_counts.drop(columns=["specialty_breakdown"])
    
    return provider_counts


def main():
    """Main entry point."""
    logger = get_logger("04_merge_datasets")
    run_id = get_run_id()

    log_step_start(logger, "load_base_geography")
    
    # Load UHF boundaries as base
    uhf_gdf = gpd.read_file(GEO_DIR / "uhf42_boundaries.geojson")
    uhf_gdf = uhf_gdf[uhf_gdf["GEOCODE"] != 0].copy()  # Remove citywide polygon
    uhf_gdf = uhf_gdf.rename(columns={"GEOCODE": "uhf_code", "GEONAME": "uhf_name", "BOROUGH": "borough"})
    
    logger.info(f"Loaded {len(uhf_gdf)} UHF neighborhoods")
    log_step_end(logger, "load_base_geography", count=len(uhf_gdf))

    # Load ER visit data
    log_step_start(logger, "load_er_data")
    er_data = load_er_data()
    logger.info(f"Loaded ER data for {len(er_data)} UHF neighborhoods")
    log_step_end(logger, "load_er_data", count=len(er_data))

    # Load population data
    log_step_start(logger, "load_population")
    pop_data = pd.read_csv(PROCESSED_DIR / "child_population_by_uhf.csv")
    logger.info(f"Loaded population for {len(pop_data)} UHF neighborhoods")
    log_step_end(logger, "load_population", count=len(pop_data))

    # Load and aggregate providers
    log_step_start(logger, "load_providers")
    providers = pd.read_csv(PROCESSED_DIR / "providers_geocoded.csv")
    provider_counts = aggregate_providers(providers)
    logger.info(f"Aggregated providers for {len(provider_counts)} UHF neighborhoods")
    log_step_end(logger, "load_providers", count=len(provider_counts))

    # Merge all data
    log_step_start(logger, "merge_datasets")
    
    # Merge ER data
    merged = uhf_gdf.merge(er_data, on="uhf_code", how="left", suffixes=("", "_er"))
    
    # Merge population
    merged = merged.merge(pop_data[["uhf_code", "child_population"]], on="uhf_code", how="left")
    
    # Merge provider counts
    merged = merged.merge(provider_counts, on="uhf_code", how="left")
    
    # Fill missing provider counts with 0
    for col in ["total_providers", "pulmonology_count", "allergy_count", "pediatrics_count"]:
        merged[col] = merged[col].fillna(0).astype(int)
    
    logger.info(f"Merged dataset has {len(merged)} rows and {len(merged.columns)} columns")
    log_step_end(logger, "merge_datasets", rows=len(merged), columns=len(merged.columns))

    # Calculate derived metrics
    log_step_start(logger, "calculate_metrics")
    
    # Provider rate per 10,000 children
    merged["providers_per_10k"] = (merged["total_providers"] / merged["child_population"]) * 10000
    merged["providers_per_10k"] = merged["providers_per_10k"].round(2)
    
    # Combined ER rate (weighted average by count if we had counts, or simple average)
    # For now, use the 5-17 age group as primary since asthma management is more relevant
    merged["er_rate_primary"] = merged["er_rate_5to17"]
    
    # Also calculate combined rate (average of both age groups)
    merged["er_rate_combined"] = ((merged["er_rate_under5"].fillna(0) + merged["er_rate_5to17"].fillna(0)) / 2).round(1)
    
    # Citywide averages for comparison
    citywide_er_rate = merged["er_rate_5to17"].mean()
    citywide_provider_rate = (merged["total_providers"].sum() / merged["child_population"].sum()) * 10000
    
    merged["er_pct_of_avg"] = ((merged["er_rate_5to17"] / citywide_er_rate) * 100).round(1)
    merged["provider_pct_of_avg"] = ((merged["providers_per_10k"] / citywide_provider_rate) * 100).round(1)
    
    logger.info(f"Citywide ER rate (5-17): {citywide_er_rate:.1f} per 10k")
    logger.info(f"Citywide provider rate: {citywide_provider_rate:.2f} per 10k children")
    log_step_end(logger, "calculate_metrics", 
                 citywide_er_rate=round(citywide_er_rate, 1),
                 citywide_provider_rate=round(citywide_provider_rate, 2))

    # QA checks
    log_qa_check(
        logger,
        "all_uhf_have_er_data",
        passed=merged["er_rate_5to17"].notna().all(),
        details=f"{merged['er_rate_5to17'].notna().sum()}/42 have ER data"
    )
    
    log_qa_check(
        logger,
        "all_uhf_have_population",
        passed=merged["child_population"].notna().all(),
        details=f"{merged['child_population'].notna().sum()}/42 have population"
    )

    # Clean up column names for output
    merged = merged.drop(columns=["uhf_name_er"], errors="ignore")
    
    # Reorder columns for clarity
    col_order = [
        "uhf_code", "uhf_name", "borough", 
        "child_population",
        "er_rate_under5", "er_rate_5to17", "er_rate_combined", "er_pct_of_avg",
        "total_providers", "pulmonology_count", "allergy_count", "pediatrics_count",
        "providers_per_10k", "provider_pct_of_avg",
        "geometry"
    ]
    merged = merged[[c for c in col_order if c in merged.columns]]

    # Write output
    output_path = PROCESSED_DIR / "uhf_analysis_data.geojson"
    atomic_write_geojson(output_path, merged)
    log_output_written(logger, output_path, row_count=len(merged))

    # Write metadata sidecar
    write_metadata_sidecar(
        data_path=output_path,
        script_name="04_merge_datasets.py",
        run_id=run_id,
        description="Merged UHF analysis dataset with ER rates, providers, and population",
        inputs=[
            "data/geo/uhf42_boundaries.geojson",
            "data/raw/asthma_er_visits_children_age 4 and under.csv",
            "data/raw/asthma_er_visits_children_age 5 to 17.csv",
            "data/processed/providers_geocoded.csv",
            "data/processed/child_population_by_uhf.csv",
        ],
        row_count=len(merged),
        columns=list(merged.columns),
        citywide_metrics={
            "er_rate_5to17": round(float(citywide_er_rate), 1),
            "provider_rate_per_10k": round(float(citywide_provider_rate), 2),
            "total_children": int(merged["child_population"].sum()),
            "total_providers": int(merged["total_providers"].sum()),
        },
    )

    logger.info(f"✓ Completed: Merged analysis dataset with {len(merged)} UHF neighborhoods")
    
    # Print summary statistics
    print("\n" + "="*60)
    print("SUMMARY STATISTICS")
    print("="*60)
    print(f"Total child population: {merged['child_population'].sum():,.0f}")
    print(f"Total providers: {merged['total_providers'].sum()}")
    print(f"Citywide ER rate (5-17): {citywide_er_rate:.1f} per 10k")
    print(f"Citywide provider rate: {citywide_provider_rate:.2f} per 10k children")
    print()
    print("ER Rate Range:")
    print(f"  Lowest:  {merged['er_rate_5to17'].min():.1f} ({merged.loc[merged['er_rate_5to17'].idxmin(), 'uhf_name']})")
    print(f"  Highest: {merged['er_rate_5to17'].max():.1f} ({merged.loc[merged['er_rate_5to17'].idxmax(), 'uhf_name']})")
    print()
    print("Provider Rate Range:")
    print(f"  Lowest:  {merged['providers_per_10k'].min():.2f} ({merged.loc[merged['providers_per_10k'].idxmin(), 'uhf_name']})")
    print(f"  Highest: {merged['providers_per_10k'].max():.2f} ({merged.loc[merged['providers_per_10k'].idxmax(), 'uhf_name']})")


if __name__ == "__main__":
    main()

