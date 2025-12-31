#!/usr/bin/env python3
"""
Script 06: Export Data for Web Visualization

Inputs:
    - data/final/uhf_classified.geojson
    - data/processed/providers_geocoded.csv

Outputs:
    - web/data/neighborhoods.geojson (simplified for web)
    - web/data/providers.geojson (provider points)
    - web/data/stats.json (summary statistics)

This script prepares data for the interactive web map.
"""
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml

from asthma_map.paths import FINAL_DIR, PROCESSED_DIR, WEB_DIR, CONFIGS_DIR
from asthma_map.io_utils import atomic_write_json, write_metadata_sidecar
from asthma_map.logging_utils import (
    get_logger,
    get_run_id,
    log_step_start,
    log_step_end,
    log_output_written,
)


def load_params() -> dict:
    """Load parameters from configs/params.yml."""
    with open(CONFIGS_DIR / "params.yml") as f:
        return yaml.safe_load(f)


def simplify_geometry(gdf: gpd.GeoDataFrame, tolerance: float = 0.0001) -> gpd.GeoDataFrame:
    """Simplify geometries to reduce file size while preserving shape."""
    gdf = gdf.copy()
    gdf["geometry"] = gdf["geometry"].simplify(tolerance, preserve_topology=True)
    return gdf


def round_coordinates(geojson_dict: dict, precision: int = 5) -> dict:
    """Round coordinates to reduce file size."""
    def round_coords(coords):
        if isinstance(coords[0], (int, float)):
            return [round(c, precision) for c in coords]
        return [round_coords(c) for c in coords]
    
    for feature in geojson_dict.get("features", []):
        geom = feature.get("geometry", {})
        if "coordinates" in geom:
            geom["coordinates"] = round_coords(geom["coordinates"])
    
    return geojson_dict


def main():
    """Main entry point."""
    logger = get_logger("06_export_for_web")
    run_id = get_run_id()

    params = load_params()
    web_data_dir = WEB_DIR / "data"
    web_data_dir.mkdir(parents=True, exist_ok=True)

    # Load classified neighborhoods
    log_step_start(logger, "load_data")
    
    uhf_gdf = gpd.read_file(FINAL_DIR / "uhf_classified.geojson")
    providers_df = pd.read_csv(PROCESSED_DIR / "providers_geocoded.csv")
    
    logger.info(f"Loaded {len(uhf_gdf)} neighborhoods and {len(providers_df)} providers")
    log_step_end(logger, "load_data")

    # Prepare neighborhoods for web
    log_step_start(logger, "prepare_neighborhoods")
    
    # Select columns for web
    web_cols = [
        "uhf_code", "uhf_name", "borough",
        "child_population",
        "er_rate_5to17", "er_pct_of_avg",
        "total_providers", "providers_per_10k", "provider_pct_of_avg",
        "er_tercile", "access_tercile", "bivariate_class", "fill_color",
        "is_failure_zone", "is_at_risk",
        "geometry"
    ]
    
    neighborhoods = uhf_gdf[[c for c in web_cols if c in uhf_gdf.columns]].copy()
    
    # Round numeric columns
    for col in ["er_rate_5to17", "providers_per_10k", "er_pct_of_avg", "provider_pct_of_avg"]:
        if col in neighborhoods.columns:
            neighborhoods[col] = neighborhoods[col].round(2)
    
    # Simplify geometries
    neighborhoods = simplify_geometry(neighborhoods)
    
    # Convert to GeoJSON and round coordinates
    neighborhoods_geojson = json.loads(neighborhoods.to_json())
    neighborhoods_geojson = round_coordinates(neighborhoods_geojson)
    
    # Write neighborhoods
    neighborhoods_path = web_data_dir / "neighborhoods.geojson"
    with open(neighborhoods_path, "w") as f:
        json.dump(neighborhoods_geojson, f)
    
    file_size = neighborhoods_path.stat().st_size / 1024
    logger.info(f"Wrote neighborhoods.geojson ({file_size:.1f} KB)")
    log_step_end(logger, "prepare_neighborhoods", file_size_kb=round(file_size, 1))

    # Prepare providers for web
    log_step_start(logger, "prepare_providers")
    
    # Filter to geocoded providers with UHF assignment
    valid_providers = providers_df[
        (providers_df["geocode_success"] == True) & 
        (providers_df["uhf_code"].notna())
    ].copy()
    
    # Select columns for web
    provider_cols = [
        "npi", "first_name", "last_name", "credential",
        "taxonomy_desc", "lat", "lon", "uhf_code", "uhf_name"
    ]
    
    valid_providers = valid_providers[[c for c in provider_cols if c in valid_providers.columns]]
    
    # Create GeoJSON features
    features = []
    for _, row in valid_providers.iterrows():
        # Handle NaN values properly
        credential = row.get("credential", "")
        if pd.isna(credential):
            credential = ""
        
        specialty = row.get("taxonomy_desc", "")
        if pd.isna(specialty):
            specialty = ""
            
        first_name = row.get("first_name", "")
        if pd.isna(first_name):
            first_name = ""
            
        last_name = row.get("last_name", "")
        if pd.isna(last_name):
            last_name = ""
        
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [round(row["lon"], 5), round(row["lat"], 5)]
            },
            "properties": {
                "npi": str(row["npi"]),
                "name": f"{first_name} {last_name}".strip(),
                "credential": str(credential),
                "specialty": str(specialty),
                "uhf_code": int(row["uhf_code"]) if pd.notna(row["uhf_code"]) else None,
            }
        }
        features.append(feature)
    
    providers_geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    # Write providers
    providers_path = web_data_dir / "providers.geojson"
    with open(providers_path, "w") as f:
        json.dump(providers_geojson, f)
    
    file_size = providers_path.stat().st_size / 1024
    logger.info(f"Wrote providers.geojson ({file_size:.1f} KB)")
    log_step_end(logger, "prepare_providers", count=len(features), file_size_kb=round(file_size, 1))

    # Calculate and export summary statistics
    log_step_start(logger, "calculate_stats")
    
    failure_zones = uhf_gdf[uhf_gdf["is_failure_zone"] == True]
    best_zones = uhf_gdf[uhf_gdf["bivariate_class"] == "1-1"]
    
    stats = {
        "total_neighborhoods": len(uhf_gdf),
        "total_children": int(uhf_gdf["child_population"].sum()),
        "total_providers": int(uhf_gdf["total_providers"].sum()),
        
        "citywide_er_rate": round(float(uhf_gdf["er_rate_5to17"].mean()), 1),
        "citywide_provider_rate": round(float(uhf_gdf["providers_per_10k"].mean()), 2),
        
        "failure_zones": {
            "count": len(failure_zones),
            "children": int(failure_zones["child_population"].sum()),
            "avg_er_rate": round(float(failure_zones["er_rate_5to17"].mean()), 1) if len(failure_zones) > 0 else 0,
            "avg_provider_rate": round(float(failure_zones["providers_per_10k"].mean()), 2) if len(failure_zones) > 0 else 0,
            "neighborhoods": failure_zones[["uhf_code", "uhf_name", "borough"]].to_dict("records"),
        },
        
        "best_zones": {
            "count": len(best_zones),
            "children": int(best_zones["child_population"].sum()),
            "avg_er_rate": round(float(best_zones["er_rate_5to17"].mean()), 1) if len(best_zones) > 0 else 0,
            "avg_provider_rate": round(float(best_zones["providers_per_10k"].mean()), 2) if len(best_zones) > 0 else 0,
            "neighborhoods": best_zones[["uhf_code", "uhf_name", "borough"]].to_dict("records"),
        },
        
        "extremes": {
            "highest_er_rate": {
                "value": round(float(uhf_gdf["er_rate_5to17"].max()), 1),
                "neighborhood": uhf_gdf.loc[uhf_gdf["er_rate_5to17"].idxmax(), "uhf_name"],
            },
            "lowest_er_rate": {
                "value": round(float(uhf_gdf["er_rate_5to17"].min()), 1),
                "neighborhood": uhf_gdf.loc[uhf_gdf["er_rate_5to17"].idxmin(), "uhf_name"],
            },
            "highest_provider_rate": {
                "value": round(float(uhf_gdf["providers_per_10k"].max()), 2),
                "neighborhood": uhf_gdf.loc[uhf_gdf["providers_per_10k"].idxmax(), "uhf_name"],
            },
            "lowest_provider_rate": {
                "value": round(float(uhf_gdf["providers_per_10k"].min()), 2),
                "neighborhood": uhf_gdf.loc[uhf_gdf["providers_per_10k"].idxmin(), "uhf_name"],
            },
        },
        
        "color_scheme": params["colors"],
        "data_year": 2023,
    }
    
    # Write stats
    stats_path = web_data_dir / "stats.json"
    atomic_write_json(stats_path, stats)
    logger.info(f"Wrote stats.json")
    log_step_end(logger, "calculate_stats")

    # Write metadata sidecar
    write_metadata_sidecar(
        data_path=neighborhoods_path,
        script_name="06_export_for_web.py",
        run_id=run_id,
        description="Web-ready GeoJSON for interactive map visualization",
        inputs=[
            "data/final/uhf_classified.geojson",
            "data/processed/providers_geocoded.csv",
        ],
        row_count=len(neighborhoods),
        output_files=[
            str(neighborhoods_path),
            str(providers_path),
            str(stats_path),
        ],
    )

    logger.info(f"✓ Completed: Exported web data")
    
    # Print summary
    print("\n" + "="*60)
    print("WEB EXPORT COMPLETE")
    print("="*60)
    print(f"\nFiles created in {web_data_dir}:")
    print(f"  • neighborhoods.geojson ({(web_data_dir / 'neighborhoods.geojson').stat().st_size / 1024:.1f} KB)")
    print(f"  • providers.geojson ({(web_data_dir / 'providers.geojson').stat().st_size / 1024:.1f} KB)")
    print(f"  • stats.json")
    print(f"\nReady for Phase 4: Visualization Development!")


if __name__ == "__main__":
    main()

