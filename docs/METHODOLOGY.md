# Methodology

## Overview

This project identifies NYC neighborhoods where the healthcare system fails children with asthma—areas with **high emergency room visit rates** combined with **low access to preventive specialists**.

## Data Sources

| Dataset | Source | Year | Notes |
|---------|--------|------|-------|
| Asthma ER Visits | NYC DOHMH | 2023 | Ages 5-17, rate per 10,000 |
| Healthcare Providers | CMS NPPES NPI Registry | 2024 | Pediatric pulmonologists & allergists |
| Child Population | US Census ACS 5-Year | 2022 | Ages 0-17 by census tract |
| Geographic Boundaries | NYC DOHMH | Current | UHF 42 neighborhoods |
| Redlining Maps | Mapping Inequality (HOLC) | 1935-1940 | Historical validation |

## Geographic Unit

We use **UHF 42 neighborhoods**—the standard geography for NYC health data. This divides the city into 42 neighborhoods that balance granularity with statistical reliability.

## Bivariate Classification

Each neighborhood is classified on two dimensions using terciles (thirds):

### Dimension 1: ER Visit Rate
- **Low (1)**: 23.2 – 87.7 per 10,000
- **Medium (2)**: 90.8 – 147.9 per 10,000  
- **High (3)**: 153.7 – 355.8 per 10,000

### Dimension 2: Specialist Access
- **High Access (1)**: 8.5 – 76.2 per 10,000
- **Medium Access (2)**: 2.9 – 7.3 per 10,000
- **Low Access (3)**: 0.0 – 2.8 per 10,000

### Failure Zone Definition
A neighborhood is a **Prevention Failure Zone** if it has:
- High ER visits (tercile 3) AND
- Low specialist access (tercile 3)

This is the deep blue color in the upper-right corner of the legend.

## Provider Selection

We queried the NPI Registry for:
- Pediatric Pulmonologists
- Pediatric Allergists  
- General Allergists (many serve children)

**1,056 providers** were identified with NYC practice addresses. Addresses were geocoded using the US Census Geocoder API (97% success rate) and spatially joined to UHF neighborhoods.

## Statistical Validation

We used **Welch's t-test** (robust to unequal variance) to compare failure zones vs other neighborhoods:

| Metric | Failure Zones | Other Zones | p-value |
|--------|---------------|-------------|---------|
| ER Rate (per 10k) | 235.6 | 122.3 | 0.008 |
| Provider Rate (per 10k) | 1.66 | 9.41 | 0.001 |

Both differences are statistically significant at p < 0.01.

## Limitations

1. **Provider location ≠ access**: Specialists may not accept Medicaid, have capacity, or be culturally accessible
2. **Cross-boundary care**: Patients travel to specialists outside their neighborhood
3. **Correlation ≠ causation**: High ER rates reflect poverty, housing, air quality, and other factors
4. **Data currency**: NPI addresses may lag actual practice locations
5. **Suppressed values**: Some ER rates have small sample sizes

## Reproducibility

All code is available in this repository. The pipeline uses:
- Python 3.11 with pandas, geopandas, shapely
- Structured JSONL logging for traceability
- Atomic file writes with metadata sidecars
- Configuration-driven parameters (no magic numbers)

Run `make all` to reproduce the full analysis.

