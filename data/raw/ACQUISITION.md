# Data Acquisition Log

## Required Datasets

| File | Source | Status | Date Acquired |
|------|--------|--------|---------------|
| asthma_er_visits_children_age 4 and under.csv | NYC DOHMH | ✅ Complete | 2024-12-30 |
| asthma_er_visits_children_age 5 to 17.csv | NYC DOHMH | ✅ Complete | 2024-12-30 |
| npi_providers_raw.json | NPI API (scripted) | ✅ Complete | 2024-12-30 |
| census_child_population_tract.csv | Census API (scripted) | ☐ Pending | |
| uhf42_boundaries.geojson | NYC Open Data | ✅ Complete | 2024-12-30 |
| nyc_holc_redlining.geojson | Richmond DSL | ☐ Optional | |

## Data Notes

### Asthma ER Visits (2023 data)
- Two files split by age group: 0-4 years and 5-17 years
- Contains multiple GeoTypes: Citywide, Borough, CD, UHF42
- We use GeoType="UHF42" for analysis (42 neighborhoods)
- Rate column: "Estimated annual rate per 10,000"

### NPI Providers
- 1,153 unique providers fetched
- Specialties: Pediatric Pulmonology (108), Allergy & Immunology (386), Pediatrics (750+)
- Note: 97 providers outside NY state will be filtered during geocoding

## Manual Downloads

### 1. Asthma ER Visits
Must be downloaded manually from NYC DOHMH Environment & Health Data Portal:
- URL: https://a816-dohbesp.nyc.gov/IndicatorPublic/data-explorer/asthma/
- Select: "Asthma emergency department visits (children 0 to 17 years old)"
- Make sure "Rate" is selected (not "Number")
- Format: CSV
- Save to: `data/raw/asthma_er_visits_children.csv`

### 2. UHF 42 Boundaries
Download from NYC Open Data:
- URL: https://data.cityofnewyork.us/Health/UHF-42-Neighborhoods/d3qk-pfyz
- Click "Export" → Select GeoJSON
- Save to: `data/geo/uhf42_boundaries.geojson`

### 3. Redlining Data (Optional, for validation)
Download from University of Richmond Digital Scholarship Lab:
- URL: https://dsl.richmond.edu/panorama/redlining/
- Or NYC-specific: https://a816-dohbesp.nyc.gov/IndicatorPublic/maps/HOLC_map/
- Format: GeoJSON
- Save to: `data/geo/nyc_holc_redlining.geojson`

## Scripted Downloads

These will be fetched automatically by pipeline scripts:

### NPI Provider Data (Script 01)
- Source: CMS NPPES NPI Registry API
- API Docs: https://npiregistry.cms.hhs.gov/api-page
- Taxonomy codes queried:
  - 2080P0301X (Pediatric Pulmonology)
  - 207K00000X (Allergy & Immunology)
  - 208000000X (Pediatrics)

### Census Population Data (Script 03)
- Source: US Census Bureau ACS 5-Year Estimates
- Table: B01001 (Sex by Age)
- Requires: Census API key (https://api.census.gov/data/key_signup.html)

## Notes

- All dates should be in ISO format (YYYY-MM-DD)
- Update this file after each acquisition
- If a URL changes or breaks, document the issue and resolution

