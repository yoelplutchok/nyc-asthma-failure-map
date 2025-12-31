# Key Findings

## Summary

This analysis reveals **4 Prevention Failure Zones** in New York City—neighborhoods where children face the worst combination of high asthma emergency room visits and low access to preventive specialists.

**221,647 children** (12.8% of NYC's child population) live in these failure zones.

---

## The Four Failure Zones

| Neighborhood | Borough | ER Rate | Providers/10k | Children |
|-------------|---------|---------|---------------|----------|
| **High Bridge - Morrisania** | Bronx | 287.9 | 2.65 | 56,652 |
| **Bedford Stuyvesant - Crown Heights** | Brooklyn | 259.1 | 1.97 | 71,124 |
| **East New York** | Brooklyn | 215.1 | 0.39 | 50,989 |
| **Northeast Bronx** | Bronx | 180.2 | 1.63 | 42,882 |

### Key Observations:
- **East New York** has the lowest specialist access in the city (0.39 per 10,000), essentially 2 specialists for 51,000 children
- **High Bridge - Morrisania** has the highest ER rate (287.9)—more than double the citywide average
- All failure zones are in the **Bronx or Brooklyn**—none in Manhattan, Queens, or Staten Island

---

## Statistical Evidence

### Failure Zones Have Significantly Higher ER Rates

| Metric | Failure Zones | Other Neighborhoods | Difference |
|--------|---------------|---------------------|------------|
| Mean ER Rate | **235.6** | 122.3 | +93% higher |
| Mean Provider Rate | **1.66** | 9.41 | 82% lower |

**Welch's t-test results:**
- ER rate difference: t = 4.14, **p = 0.008** ✓
- Provider rate difference: t = -3.42, **p = 0.001** ✓

Both differences are statistically significant at the 99% confidence level.

---

## The Redlining Connection

### Historical Discrimination Predicts Current Health Outcomes

I analyzed the overlap between today's asthma failure zones and neighborhoods that were "redlined" (marked as hazardous for lending) in the 1930s.

| Zone Type | % Historically Redlined |
|-----------|------------------------|
| Failure Zones | **36.4%** |
| Other Neighborhoods | 21.7% |

**Failure zones are 68% more likely to overlap with historically redlined areas.**

### Correlation Analysis

| Relationship | Pearson r | p-value |
|-------------|-----------|---------|
| Redlining ↔ ER Rate | **0.47** | **0.002** |

This is a **moderately strong, highly significant correlation**. Neighborhoods that were marked as "hazardous" 90 years ago have significantly higher childhood asthma ER rates today.

### Most Impacted Neighborhoods

| Neighborhood | % Redlined | ER Rate | Status |
|-------------|------------|---------|--------|
| Central Harlem | 69.8% | 345.8 | At Risk |
| Williamsburg - Bushwick | 69.8% | 159.4 | At Risk |
| East Harlem | 50.4% | 355.8 | At Risk |
| Bedford Stuyvesant | 57.3% | 259.1 | **Failure Zone** |

---

## Provider Distribution Disparity

When you toggle "Show Providers" on the map, the disparity becomes starkly visible:

- **Manhattan**: Dense cluster of specialists, especially around major medical centers
- **Failure Zones**: Sparse coverage, sometimes only 1-2 providers for neighborhoods of 50,000+ children

### The Access Gap

| Metric | Top Tercile | Bottom Tercile | Gap |
|--------|------------|----------------|-----|
| Providers per 10k | 8.5 – 76.2 | 0.0 – 2.8 | 27x |

The best-served neighborhoods have **27 times more specialists per capita** than the worst-served.

---

## What This Means

### For Children
Kids in failure zones are more likely to:
- End up in the emergency room for preventable asthma attacks
- Lack access to specialists who could provide ongoing care
- Face longer travel times to reach appropriate providers

### For the Healthcare System
- ER visits are expensive, and preventive care is cheaper
- Specialist shortages in underserved areas persist despite overall provider growth
- Geographic maldistribution of providers compounds health inequity

### For Policy
- **Targeted recruitment**: Incentivize specialists to practice in underserved neighborhoods
- **Medicaid access**: Ensure providers in these areas accept public insurance
- **Telehealth**: Expand remote consultations to bridge geographic gaps
- **School-based care**: Bring asthma management directly to children

---

## Limitations of These Findings

1. **Association, not causation**: We cannot prove that low specialist access *causes* high ER visits; other factors (poverty, housing quality, air pollution) likely play significant roles

2. **Provider location ≠ true access**: A specialist in a neighborhood may not accept Medicaid, be taking new patients, or have short wait times

3. **Cross-neighborhood care**: Many patients travel to Manhattan for specialty care; neighborhood counts don't capture this

4. **No direct ER-to-Provider correlation**: At the neighborhood level, I found no significant correlation (r = -0.035, p = 0.83) between provider rates and ER rates, suggesting other factors dominate

---

## Data Quality Notes

- **1,056 providers** identified and geocoded (97% success rate)
- **42 UHF neighborhoods** analyzed
- **1,733,977 children** in population denominator
- **403 HOLC zones** analyzed for redlining correlation
- Statistical tests used Welch's t-test (robust to unequal variance)
- Area calculations used EPSG:2263 projection (NY State Plane)

---

*Analysis completed December 2024. See [METHODOLOGY.md](METHODOLOGY.md) for technical details.*

