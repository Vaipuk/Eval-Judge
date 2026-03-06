# Comparison Report

**legacy-v1.0** vs **unified-v2.1**

*Generated on 2026-03-02 14:05:56*

## Summary

- **Baseline Run:** eval-legacy-v1.0-20260227-042136 (legacy-v1.0)
- **Comparison Run:** eval-unified-v2.1-20260227-154224 (unified-v2.1)
- **Matched Inputs:** 50

## Script Quality Comparison

| Metric | legacy-v1.0 | unified-v2.1 | Delta | Significance |
|--------|--------------|--------------|-------|--------------|
| **Script Quality** | 3.35 | 3.26 | -0.09 | (p=N/A) |

> **Result:** No statistically significant change in Script Quality

### Script Quality Dimensions

| Dimension | legacy-v1.0 | unified-v2.1 | Delta | Status |
|-----------|--------------|--------------|-------|--------|
| Hook Quality | 3.40 | 3.24 | -0.16 | No change |
| Tone Match | 3.46 | 3.16 | -0.30 | No change |
| Structural Flow | 3.54 | 3.36 | -0.18 | No change |
| Content Richness | 2.53 | 2.59 | +0.06 | No change |
| Completeness | 3.83 | 3.91 | +0.09 | No change |

## System Metrics Comparison

*Simple mean delta (no statistical test)*

| Metric | legacy-v1.0 | unified-v2.1 | Delta |
|--------|--------------|--------------|-------|
| Timing Accuracy | 4.08 | 4.02 | -0.06 |
| Template Compatibility | 2.86 | 3.46 | +0.60 |

## Feedback Theme Changes

### Resolved Themes

*These issues appeared in the baseline but not in the new version:*

- **Template: Only 2 categories triggered** (was 5 occurrences)
- **Template: TITLE overrepresented: 16.7% (target: 5%...** (was 5 occurrences)
- **Template: TITLE overrepresented: 14.3% (target: 5%...** (was 6 occurrences)

### New Themes

*These issues appeared in the new version but not in the baseline:*

- **Template: LIST overrepresented: 25.0% (target: 15%...** (4 occurrences)
- **Template: LIST overrepresented: 31.2% (target: 15%...** (5 occurrences)
- **Template: LIST overrepresented: 33.3% (target: 15%...** (5 occurrences)

### Persistent Themes

*These issues appear in both versions:*

| Theme | Baseline | New | Change |
|-------|----------|-----|--------|
| Template: LIST underrepresented: 0.0% (target: 15%... | 22 | 7 | -15 |
| Template: QUOTE underrepresented: 0.0% (target: 10... | 45 | 47 | +2 |
| Template: DEFAULT overrepresented: 50.0% (target: ... | 5 | 8 | +3 |
| Template: SECTION underrepresented: 0.0% (target: ... | 35 | 34 | -1 |
| Template: NUMBER underrepresented: 0.0% (target: 1... | 41 | 27 | -14 |
| Template: EMPHASIS underrepresented: 0.0% (target:... | 11 | 5 | -6 |
| Template: No SECTION scenes despite script length ... | 10 | 33 | +23 |
