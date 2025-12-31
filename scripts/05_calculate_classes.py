#!/usr/bin/env python3
"""
Script 05: Calculate Bivariate Classifications

Input:  data/processed/uhf_analysis_data.geojson
Output: data/final/uhf_classified.geojson

This script:
1. Calculates terciles for ER visit rates and provider access
2. Creates bivariate classification codes (e.g., "3-3" = high ER, low access)
3. Assigns colors based on the bivariate color scheme
4. Identifies critical failure zones
"""
import geopandas as gpd
import pandas as pd
import yaml

from asthma_map.paths import PROCESSED_DIR, FINAL_DIR, CONFIGS_DIR
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


def calculate_terciles(series: pd.Series, reverse: bool = False) -> pd.Series:
    """
    Calculate tercile classification (1, 2, 3) for a numeric series.
    
    If reverse=True, higher values get lower class (used for provider access
    where more providers = better = 1).
    """
    # Handle zeros specially for provider data
    terciles = pd.qcut(series, q=3, labels=False, duplicates="drop") + 1
    
    if reverse:
        # Invert: 1->3, 2->2, 3->1
        terciles = 4 - terciles
    
    return terciles


def main():
    """Main entry point."""
    logger = get_logger("05_calculate_classes")
    run_id = get_run_id()

    # Load configuration
    params = load_params()
    colors = params["colors"]

    # Load merged data
    log_step_start(logger, "load_data")
    
    input_path = PROCESSED_DIR / "uhf_analysis_data.geojson"
    gdf = gpd.read_file(input_path)
    
    logger.info(f"Loaded {len(gdf)} UHF neighborhoods")
    log_step_end(logger, "load_data", count=len(gdf))

    # Calculate terciles
    log_step_start(logger, "calculate_terciles")
    
    # ER Rate: Higher = worse = 3
    gdf["er_tercile"] = calculate_terciles(gdf["er_rate_5to17"], reverse=False)
    
    # Provider Rate: Higher = better, so reverse (high providers = 1, low providers = 3)
    gdf["access_tercile"] = calculate_terciles(gdf["providers_per_10k"], reverse=True)
    
    # Create bivariate class code
    gdf["bivariate_class"] = gdf["er_tercile"].astype(str) + "-" + gdf["access_tercile"].astype(str)
    
    # Assign colors
    gdf["fill_color"] = gdf["bivariate_class"].map(colors)
    
    # Log tercile distributions
    logger.info("ER Rate Terciles:")
    for t in [1, 2, 3]:
        subset = gdf[gdf["er_tercile"] == t]
        logger.info(f"  Tercile {t}: {len(subset)} neighborhoods, "
                   f"rate range {subset['er_rate_5to17'].min():.1f} - {subset['er_rate_5to17'].max():.1f}")
    
    logger.info("Access Terciles:")
    for t in [1, 2, 3]:
        subset = gdf[gdf["access_tercile"] == t]
        logger.info(f"  Tercile {t}: {len(subset)} neighborhoods, "
                   f"provider rate range {subset['providers_per_10k'].min():.2f} - {subset['providers_per_10k'].max():.2f}")
    
    log_step_end(logger, "calculate_terciles")

    # Identify failure zones
    log_step_start(logger, "identify_failure_zones")
    
    # Critical failure zone: High ER (3) AND Low Access (3)
    gdf["is_failure_zone"] = (gdf["er_tercile"] == 3) & (gdf["access_tercile"] == 3)
    
    failure_zones = gdf[gdf["is_failure_zone"]]
    logger.info(f"Identified {len(failure_zones)} critical failure zones:")
    for _, row in failure_zones.iterrows():
        logger.info(f"  - {row['uhf_name']} ({row['borough']}): "
                   f"ER={row['er_rate_5to17']:.1f}, providers={row['providers_per_10k']:.2f}")
    
    # Also identify "at risk" zones: High ER with Medium Access, or Medium ER with Low Access
    gdf["is_at_risk"] = ((gdf["er_tercile"] == 3) & (gdf["access_tercile"] == 2)) | \
                         ((gdf["er_tercile"] == 2) & (gdf["access_tercile"] == 3))
    
    at_risk = gdf[gdf["is_at_risk"]]
    logger.info(f"Identified {len(at_risk)} at-risk zones")
    
    log_step_end(logger, "identify_failure_zones", 
                 failure_count=len(failure_zones),
                 at_risk_count=len(at_risk))

    # Calculate summary statistics for each zone type
    log_step_start(logger, "calculate_statistics")
    
    # Best zones (1-1): Low ER, High Access
    best_zones = gdf[gdf["bivariate_class"] == "1-1"]
    
    # Citywide averages
    citywide_er = gdf["er_rate_5to17"].mean()
    citywide_providers = gdf["providers_per_10k"].mean()
    
    # Failure zone averages
    if len(failure_zones) > 0:
        failure_er_avg = failure_zones["er_rate_5to17"].mean()
        failure_provider_avg = failure_zones["providers_per_10k"].mean()
        failure_pop = failure_zones["child_population"].sum()
        
        logger.info(f"Failure Zone Statistics:")
        logger.info(f"  Average ER rate: {failure_er_avg:.1f} (citywide: {citywide_er:.1f})")
        logger.info(f"  Average provider rate: {failure_provider_avg:.2f} (citywide: {citywide_providers:.2f})")
        logger.info(f"  Total children affected: {failure_pop:,}")
    
    log_step_end(logger, "calculate_statistics")

    # QA checks
    log_qa_check(
        logger,
        "all_have_classification",
        passed=gdf["bivariate_class"].notna().all(),
        details=f"{gdf['bivariate_class'].notna().sum()}/42 classified"
    )
    
    log_qa_check(
        logger,
        "all_have_colors",
        passed=gdf["fill_color"].notna().all(),
        details=f"{gdf['fill_color'].notna().sum()}/42 have colors"
    )
    
    # Verify we have 9 possible classes
    unique_classes = gdf["bivariate_class"].nunique()
    log_qa_check(
        logger,
        "bivariate_distribution",
        passed=unique_classes >= 6,
        details=f"Found {unique_classes} unique bivariate classes"
    )

    # Prepare output columns
    output_cols = [
        "uhf_code", "uhf_name", "borough",
        "child_population",
        "er_rate_under5", "er_rate_5to17", "er_rate_combined", "er_pct_of_avg",
        "total_providers", "pulmonology_count", "allergy_count", "pediatrics_count",
        "providers_per_10k", "provider_pct_of_avg",
        "er_tercile", "access_tercile", "bivariate_class", "fill_color",
        "is_failure_zone", "is_at_risk",
        "geometry"
    ]
    gdf = gdf[[c for c in output_cols if c in gdf.columns]]

    # Write output
    output_path = FINAL_DIR / "uhf_classified.geojson"
    atomic_write_geojson(output_path, gdf)
    log_output_written(logger, output_path, row_count=len(gdf))

    # Write metadata sidecar
    write_metadata_sidecar(
        data_path=output_path,
        script_name="05_calculate_classes.py",
        run_id=run_id,
        description="UHF neighborhoods with bivariate classification for ER rates vs provider access",
        inputs=[str(input_path)],
        row_count=len(gdf),
        columns=list(gdf.columns),
        classification={
            "method": "terciles",
            "er_dimension": "er_rate_5to17 (higher=worse=3)",
            "access_dimension": "providers_per_10k (lower=worse=3)",
            "failure_zone_class": "3-3",
            "failure_zone_count": len(failure_zones),
            "at_risk_count": len(at_risk),
        },
        citywide_averages={
            "er_rate": round(float(citywide_er), 1),
            "provider_rate": round(float(citywide_providers), 2),
        },
    )

    # Print summary
    print("\n" + "="*60)
    print("BIVARIATE CLASSIFICATION SUMMARY")
    print("="*60)
    print("\nClass Distribution:")
    class_counts = gdf["bivariate_class"].value_counts().sort_index()
    for cls, count in class_counts.items():
        label = ""
        if cls == "3-3":
            label = " ← FAILURE ZONE"
        elif cls == "1-1":
            label = " ← Best"
        print(f"  {cls}: {count} neighborhoods{label}")
    
    print(f"\n🚨 CRITICAL FAILURE ZONES ({len(failure_zones)}):")
    for _, row in failure_zones.iterrows():
        print(f"  • {row['uhf_name']} ({row['borough']})")
        print(f"    ER Rate: {row['er_rate_5to17']:.1f} per 10k ({row['er_pct_of_avg']:.0f}% of avg)")
        print(f"    Providers: {row['total_providers']} ({row['providers_per_10k']:.2f} per 10k)")
        print(f"    Children: {row['child_population']:,}")

    logger.info(f"✓ Completed: Classified {len(gdf)} neighborhoods, {len(failure_zones)} failure zones identified")


if __name__ == "__main__":
    main()

