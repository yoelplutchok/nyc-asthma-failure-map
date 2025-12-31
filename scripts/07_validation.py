#!/usr/bin/env python3
"""
Script 07: Statistical Validation

Performs validation tests on the analysis:
1. Correlation between ER rates and provider access
2. T-test comparing failure zones vs other neighborhoods
3. Redlining (HOLC) correlation analysis
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from scipy import stats
import numpy as np
import pandas as pd
import geopandas as gpd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from asthma_map.paths import FINAL_DIR, GEO_DIR, LOGS_DIR
from asthma_map.logging_utils import get_logger, log_step_start, log_step_end

logger = get_logger(__name__)


def load_analysis_data():
    """Load the classified analysis data."""
    log_step_start(logger, "load_data", description="Loading analysis data")
    
    gdf = gpd.read_file(FINAL_DIR / "uhf_classified.geojson")
    logger.info(f"Loaded {len(gdf)} neighborhoods")
    
    log_step_end(logger, "load_data", status="success")
    return gdf


def load_redlining_data():
    """Load HOLC redlining data."""
    log_step_start(logger, "load_redlining", description="Loading HOLC redlining data")
    
    holc_path = GEO_DIR / "nyc_holc_redlining.geojson"
    if not holc_path.exists():
        logger.warning("HOLC redlining data not found")
        log_step_end(logger, "load_redlining", status="skipped")
        return None
    
    holc = gpd.read_file(holc_path)
    logger.info(f"Loaded {len(holc)} HOLC zones")
    
    log_step_end(logger, "load_redlining", status="success")
    return holc


def correlation_analysis(gdf):
    """Test correlation between ER rates and provider access."""
    log_step_start(logger, "correlation", description="Testing ER rate vs provider correlation")
    
    # Get valid data
    valid = gdf[
        (gdf["er_rate_5to17"].notna()) & 
        (gdf["providers_per_10k"].notna())
    ].copy()
    
    er_rates = valid["er_rate_5to17"].values
    provider_rates = valid["providers_per_10k"].values
    
    # Pearson correlation
    r, p_value = stats.pearsonr(er_rates, provider_rates)
    
    # Spearman correlation (rank-based, more robust)
    rho, p_spearman = stats.spearmanr(er_rates, provider_rates)
    
    results = {
        "n_observations": len(valid),
        "pearson_r": round(r, 4),
        "pearson_p": round(p_value, 6),
        "spearman_rho": round(rho, 4),
        "spearman_p": round(p_spearman, 6),
        "interpretation": ""
    }
    
    # Interpret
    if p_value < 0.05:
        if r < 0:
            results["interpretation"] = f"Significant NEGATIVE correlation (r={r:.3f}, p={p_value:.4f}): " \
                "Higher provider access is associated with LOWER ER rates."
        else:
            results["interpretation"] = f"Significant POSITIVE correlation (r={r:.3f}, p={p_value:.4f}): " \
                "Higher provider access is associated with HIGHER ER rates (unexpected)."
    else:
        results["interpretation"] = f"No significant correlation (r={r:.3f}, p={p_value:.4f})"
    
    logger.info(f"Pearson r = {r:.4f} (p = {p_value:.6f})")
    logger.info(f"Spearman ρ = {rho:.4f} (p = {p_spearman:.6f})")
    logger.info(f"Interpretation: {results['interpretation']}")
    
    log_step_end(logger, "correlation", status="success")
    return results


def failure_zone_ttest(gdf):
    """Compare failure zones to other neighborhoods."""
    log_step_start(logger, "ttest", description="T-test: Failure zones vs others")
    
    failure = gdf[gdf["is_failure_zone"] == True]
    non_failure = gdf[gdf["is_failure_zone"] == False]
    
    results = {
        "failure_zones": {
            "count": len(failure),
            "mean_er_rate": round(failure["er_rate_5to17"].mean(), 2),
            "mean_provider_rate": round(failure["providers_per_10k"].mean(), 2),
            "total_children": int(failure["child_population"].sum())
        },
        "other_zones": {
            "count": len(non_failure),
            "mean_er_rate": round(non_failure["er_rate_5to17"].mean(), 2),
            "mean_provider_rate": round(non_failure["providers_per_10k"].mean(), 2),
            "total_children": int(non_failure["child_population"].sum())
        },
        "tests": {}
    }
    
    # Welch's t-test for ER rates (doesn't assume equal variance, more robust)
    t_er, p_er = stats.ttest_ind(
        failure["er_rate_5to17"].dropna(),
        non_failure["er_rate_5to17"].dropna(),
        equal_var=False  # Welch's t-test
    )
    results["tests"]["er_rate_ttest"] = {
        "t_statistic": round(t_er, 4),
        "p_value": round(p_er, 6),
        "significant": bool(p_er < 0.05),
        "test_type": "Welch's t-test"
    }

    # Welch's t-test for provider rates
    t_prov, p_prov = stats.ttest_ind(
        failure["providers_per_10k"].dropna(),
        non_failure["providers_per_10k"].dropna(),
        equal_var=False  # Welch's t-test
    )
    results["tests"]["provider_rate_ttest"] = {
        "t_statistic": round(t_prov, 4),
        "p_value": round(p_prov, 6),
        "significant": bool(p_prov < 0.05),
        "test_type": "Welch's t-test"
    }
    
    logger.info(f"Failure zones (n={len(failure)}): ER={results['failure_zones']['mean_er_rate']}, Providers={results['failure_zones']['mean_provider_rate']}")
    logger.info(f"Other zones (n={len(non_failure)}): ER={results['other_zones']['mean_er_rate']}, Providers={results['other_zones']['mean_provider_rate']}")
    logger.info(f"ER rate t-test: t={t_er:.3f}, p={p_er:.6f}")
    logger.info(f"Provider rate t-test: t={t_prov:.3f}, p={p_prov:.6f}")
    
    log_step_end(logger, "ttest", status="success")
    return results


def redlining_analysis(gdf, holc):
    """Analyze overlap between failure zones and historically redlined areas."""
    log_step_start(logger, "redlining", description="Analyzing redlining correlation")

    if holc is None:
        logger.warning("Skipping redlining analysis - no HOLC data")
        log_step_end(logger, "redlining", status="skipped")
        return None

    # Project to NY State Plane for accurate area calculations
    projected_crs = "EPSG:2263"
    gdf_proj = gdf.to_crs(projected_crs)
    holc_proj = holc.to_crs(projected_crs)

    # Filter to Grade D (redlined) areas
    redlined = holc_proj[holc_proj["grade"] == "D"]
    logger.info(f"Found {len(redlined)} Grade D (redlined) zones")

    if len(redlined) == 0:
        logger.warning("No Grade D zones found in HOLC data")
        log_step_end(logger, "redlining", status="skipped")
        return None

    # Calculate overlap for each UHF neighborhood
    results = []

    for idx, row in gdf_proj.iterrows():
        uhf_geom = row.geometry

        # Calculate area of intersection with redlined zones (in projected CRS)
        intersections = redlined.geometry.intersection(uhf_geom)
        redlined_area = intersections.area.sum()
        total_area = uhf_geom.area
        pct_redlined = (redlined_area / total_area) * 100 if total_area > 0 else 0
        
        results.append({
            "uhf_code": row.get("uhf_code", row.get("UHFCODE")),
            "uhf_name": row.get("uhf_name", row.get("UHF_NEIGH")),
            "is_failure_zone": row.get("is_failure_zone", False),
            "pct_historically_redlined": round(pct_redlined, 2),
            "er_rate": row.get("er_rate_5to17"),
            "providers_per_10k": row.get("providers_per_10k")
        })
    
    results_df = pd.DataFrame(results)
    
    # Compare redlining in failure vs non-failure zones
    failure_redlined = results_df[results_df["is_failure_zone"] == True]["pct_historically_redlined"].mean()
    other_redlined = results_df[results_df["is_failure_zone"] == False]["pct_historically_redlined"].mean()
    
    # Correlation between redlining and ER rates
    valid = results_df[results_df["er_rate"].notna()]
    if len(valid) > 5:
        r_redline_er, p_redline_er = stats.pearsonr(
            valid["pct_historically_redlined"],
            valid["er_rate"]
        )
    else:
        r_redline_er, p_redline_er = np.nan, np.nan
    
    analysis = {
        "total_neighborhoods": len(results_df),
        "avg_pct_redlined_failure_zones": round(failure_redlined, 2) if not np.isnan(failure_redlined) else None,
        "avg_pct_redlined_other_zones": round(other_redlined, 2) if not np.isnan(other_redlined) else None,
        "correlation_redlining_er_rate": {
            "r": round(r_redline_er, 4) if not np.isnan(r_redline_er) else None,
            "p": round(p_redline_er, 6) if not np.isnan(p_redline_er) else None
        },
        "top_redlined_neighborhoods": results_df.nlargest(5, "pct_historically_redlined")[
            ["uhf_name", "pct_historically_redlined", "is_failure_zone", "er_rate"]
        ].to_dict(orient="records")
    }
    
    logger.info(f"Avg % redlined in failure zones: {failure_redlined:.1f}%")
    logger.info(f"Avg % redlined in other zones: {other_redlined:.1f}%")
    logger.info(f"Redlining-ER correlation: r={r_redline_er:.3f}, p={p_redline_er:.4f}")
    
    log_step_end(logger, "redlining", status="success")
    return analysis


def save_validation_report(correlation, ttest, redlining):
    """Save validation results to JSON."""
    log_step_start(logger, "save_report", description="Saving validation report")
    
    report = {
        "generated_at": datetime.now().isoformat(),
        "correlation_analysis": correlation,
        "ttest_analysis": ttest,
        "redlining_analysis": redlining
    }
    
    output_path = FINAL_DIR / "validation_report.json"
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    logger.info(f"Saved validation report to {output_path}")
    log_step_end(logger, "save_report", status="success")
    
    return report


def print_summary(correlation, ttest, redlining):
    """Print a formatted summary of validation results."""
    print("\n" + "=" * 60)
    print("VALIDATION REPORT")
    print("=" * 60)
    
    print("\n📊 CORRELATION ANALYSIS")
    print("-" * 40)
    print(f"Observations: {correlation['n_observations']}")
    print(f"Pearson r: {correlation['pearson_r']} (p = {correlation['pearson_p']})")
    print(f"Spearman ρ: {correlation['spearman_rho']} (p = {correlation['spearman_p']})")
    print(f"\n→ {correlation['interpretation']}")
    
    print("\n📈 T-TEST: Failure Zones vs Other Neighborhoods")
    print("-" * 40)
    print(f"Failure zones (n={ttest['failure_zones']['count']}):")
    print(f"  - Mean ER rate: {ttest['failure_zones']['mean_er_rate']} per 10k")
    print(f"  - Mean provider rate: {ttest['failure_zones']['mean_provider_rate']} per 10k")
    print(f"  - Children affected: {ttest['failure_zones']['total_children']:,}")
    print(f"\nOther zones (n={ttest['other_zones']['count']}):")
    print(f"  - Mean ER rate: {ttest['other_zones']['mean_er_rate']} per 10k")
    print(f"  - Mean provider rate: {ttest['other_zones']['mean_provider_rate']} per 10k")
    print(f"\nER Rate difference:")
    print(f"  t = {ttest['tests']['er_rate_ttest']['t_statistic']}, p = {ttest['tests']['er_rate_ttest']['p_value']}")
    print(f"  Significant: {'✓ YES' if ttest['tests']['er_rate_ttest']['significant'] else '✗ NO'}")
    print(f"\nProvider Rate difference:")
    print(f"  t = {ttest['tests']['provider_rate_ttest']['t_statistic']}, p = {ttest['tests']['provider_rate_ttest']['p_value']}")
    print(f"  Significant: {'✓ YES' if ttest['tests']['provider_rate_ttest']['significant'] else '✗ NO'}")
    
    if redlining:
        print("\n🏚️ REDLINING (HOLC) ANALYSIS")
        print("-" * 40)
        print(f"Avg % redlined in failure zones: {redlining['avg_pct_redlined_failure_zones']}%")
        print(f"Avg % redlined in other zones: {redlining['avg_pct_redlined_other_zones']}%")
        if redlining['correlation_redlining_er_rate']['r']:
            print(f"\nRedlining-ER rate correlation:")
            print(f"  r = {redlining['correlation_redlining_er_rate']['r']}, p = {redlining['correlation_redlining_er_rate']['p']}")
        print(f"\nTop 5 historically redlined neighborhoods:")
        for hood in redlining['top_redlined_neighborhoods']:
            flag = "🚨" if hood['is_failure_zone'] else "  "
            print(f"  {flag} {hood['uhf_name']}: {hood['pct_historically_redlined']}% redlined, ER={hood['er_rate']}")
    
    print("\n" + "=" * 60)


def main():
    """Run all validation tests."""
    print("=" * 60)
    print("SCRIPT 07: STATISTICAL VALIDATION")
    print("=" * 60)
    
    # Load data
    gdf = load_analysis_data()
    holc = load_redlining_data()
    
    # Run analyses
    correlation = correlation_analysis(gdf)
    ttest = failure_zone_ttest(gdf)
    redlining = redlining_analysis(gdf, holc)
    
    # Save report
    save_validation_report(correlation, ttest, redlining)
    
    # Print summary
    print_summary(correlation, ttest, redlining)
    
    logger.info("✓ Completed: Validation analysis")


if __name__ == "__main__":
    main()

