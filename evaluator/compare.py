"""
Cross-Run Comparison

Compares two evaluation runs to detect improvements and regressions.
Uses Wilcoxon signed-rank test for statistical significance.
"""

import json
from pathlib import Path
from typing import Optional

# Lazy import for scipy to avoid NumPy version conflicts at module load
_wilcoxon_func = None
_scipy_checked = False


def _get_wilcoxon():
    """Lazily import scipy.stats.wilcoxon."""
    global _wilcoxon_func, _scipy_checked
    if _scipy_checked:
        return _wilcoxon_func

    _scipy_checked = True
    try:
        from scipy.stats import wilcoxon
        _wilcoxon_func = wilcoxon
    except (ImportError, RuntimeError, Exception):
        _wilcoxon_func = None

    return _wilcoxon_func

from judge.config import SCRIPT_QUALITY_DIMENSIONS, SYSTEM_METRIC_DIMENSIONS

PROJECT_ROOT = Path(__file__).parent.parent
RUNS_DIR = PROJECT_ROOT / "data" / "runs"

# All scoring dimensions (for backward compatibility)
DIMENSIONS = SCRIPT_QUALITY_DIMENSIONS + SYSTEM_METRIC_DIMENSIONS

# Thresholds for significance
SIGNIFICANCE_THRESHOLD = 0.05  # p-value threshold
DELTA_THRESHOLD = 0.3  # minimum meaningful score change


def _load_run_result(run_id: str) -> dict:
    """Load a run result from JSON file."""
    run_path = RUNS_DIR / f"{run_id}.json"
    if not run_path.exists():
        raise FileNotFoundError(f"Run result not found: {run_path}")

    with open(run_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_aggregation(run_id: str) -> Optional[dict]:
    """Load aggregation result if it exists."""
    agg_path = RUNS_DIR / f"{run_id}_aggregation.json"
    if not agg_path.exists():
        return None

    with open(agg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _match_results_by_input(run1_results: list, run2_results: list) -> list[tuple[dict, dict]]:
    """
    Match results from two runs by test input ID.

    Returns list of (run1_result, run2_result) pairs for matched inputs.
    """
    # Build lookup by input ID
    run1_by_id = {r.get("script_id"): r for r in run1_results}
    run2_by_id = {r.get("script_id"): r for r in run2_results}

    # Find matching IDs
    common_ids = set(run1_by_id.keys()) & set(run2_by_id.keys())

    pairs = []
    for input_id in common_ids:
        pairs.append((run1_by_id[input_id], run2_by_id[input_id]))

    return pairs


def _extract_paired_scores(
    pairs: list[tuple[dict, dict]],
    dimension: str,
) -> tuple[list[float], list[float]]:
    """
    Extract paired scores for a dimension from matched results.

    Returns (run1_scores, run2_scores) with matching indices.
    Only includes pairs where both scores are valid.
    """
    run1_scores = []
    run2_scores = []

    for r1, r2 in pairs:
        score1 = r1.get("scores", {}).get(dimension, {}).get("score")
        score2 = r2.get("scores", {}).get(dimension, {}).get("score")

        if score1 is not None and score2 is not None:
            run1_scores.append(float(score1))
            run2_scores.append(float(score2))

    return run1_scores, run2_scores


def _wilcoxon_test(
    scores1: list[float],
    scores2: list[float],
) -> tuple[Optional[float], Optional[float]]:
    """
    Run Wilcoxon signed-rank test on paired scores.

    Returns (statistic, p_value) or (None, None) if test cannot be run.
    """
    wilcoxon = _get_wilcoxon()
    if wilcoxon is None:
        return None, None

    if len(scores1) < 5:
        return None, None  # Need at least 5 pairs

    # Calculate differences
    diffs = [s2 - s1 for s1, s2 in zip(scores1, scores2)]

    # Check if all differences are zero
    if all(d == 0 for d in diffs):
        return 0.0, 1.0  # No difference

    try:
        stat, p_value = wilcoxon(scores1, scores2, alternative='two-sided')
        return float(stat), float(p_value)
    except Exception:
        return None, None


def _classify_change(
    delta: float,
    p_value: Optional[float],
) -> str:
    """
    Classify a score change as improvement, regression, or no change.

    Returns one of:
    - "IMPROVED" (increase >= 0.3, p < 0.05)
    - "REGRESSION" (decrease >= 0.3, p < 0.05)
    - "NO_CHANGE" (not significant or small delta)
    """
    is_significant = p_value is not None and p_value < SIGNIFICANCE_THRESHOLD

    if abs(delta) >= DELTA_THRESHOLD and is_significant:
        if delta > 0:
            return "IMPROVED"
        else:
            return "REGRESSION"

    return "NO_CHANGE"


def _diff_feedback_themes(
    themes1: list[dict],
    themes2: list[dict],
) -> dict:
    """
    Compare feedback themes between two runs.

    Returns:
    - resolved: Themes present in run1 but not in run2
    - persistent: Themes present in both
    - new: Themes present in run2 but not in run1
    """
    # Use theme names for comparison
    names1 = {t.get("name", ""): t for t in themes1}
    names2 = {t.get("name", ""): t for t in themes2}

    set1 = set(names1.keys())
    set2 = set(names2.keys())

    # For more sophisticated matching, we could use string similarity
    # For now, use exact name matching
    resolved = []
    for name in set1 - set2:
        resolved.append(names1[name])

    persistent = []
    for name in set1 & set2:
        persistent.append({
            "name": name,
            "run1_count": names1[name].get("count", 0),
            "run2_count": names2[name].get("count", 0),
        })

    new = []
    for name in set2 - set1:
        new.append(names2[name])

    return {
        "resolved": resolved,
        "persistent": persistent,
        "new": new,
    }


def compare_runs(
    run1_id: str,
    run2_id: str,
    run1_result: Optional[dict] = None,
    run2_result: Optional[dict] = None,
) -> dict:
    """
    Compare two evaluation runs.

    Args:
        run1_id: ID of the baseline run
        run2_id: ID of the comparison run
        run1_result: Optional pre-loaded run1 result
        run2_result: Optional pre-loaded run2 result

    Returns:
        Comparison result with per-dimension analysis and theme diff
    """
    # Load runs if not provided
    if run1_result is None:
        run1_result = _load_run_result(run1_id)
    if run2_result is None:
        run2_result = _load_run_result(run2_id)

    # Match results by input ID
    pairs = _match_results_by_input(
        run1_result.get("results", []),
        run2_result.get("results", []),
    )

    if not pairs:
        return {
            "error": "No matching test inputs found between runs",
            "run1_id": run1_id,
            "run2_id": run2_id,
        }

    comparison = {
        "run1_id": run1_id,
        "run2_id": run2_id,
        "run1_prompt": run1_result.get("prompt_version"),
        "run2_prompt": run2_result.get("prompt_version"),
        "matched_inputs": len(pairs),
        # New structure: separate script quality from system metrics
        "script_quality": {},  # Wilcoxon test for statistical significance
        "system_metrics": {    # Simple mean delta comparison
            "timing_accuracy": {},
            "template_compatibility": {},
        },
        "overall": {},  # Legacy: weighted composite
        "by_dimension": {},
        "improvements": [],
        "regressions": [],
        "feedback_theme_diff": {},
    }

    # === Script Quality Comparison (Wilcoxon test) ===
    run1_script_quality = [r1.get("script_quality_score", 0) for r1, _ in pairs]
    run2_script_quality = [r2.get("script_quality_score", 0) for _, r2 in pairs]

    if run1_script_quality and run2_script_quality:
        mean1 = sum(run1_script_quality) / len(run1_script_quality)
        mean2 = sum(run2_script_quality) / len(run2_script_quality)
        delta = mean2 - mean1

        stat, p_value = _wilcoxon_test(run1_script_quality, run2_script_quality)
        classification = _classify_change(delta, p_value)

        comparison["script_quality"] = {
            "run1_mean": round(mean1, 2),
            "run2_mean": round(mean2, 2),
            "delta": round(delta, 2),
            "p_value": round(p_value, 4) if p_value is not None else None,
            "classification": classification,
        }

        if classification == "IMPROVED":
            comparison["improvements"].append("Script Quality")
        elif classification == "REGRESSION":
            comparison["regressions"].append("Script Quality")

    # === System Metrics Comparison (simple mean delta, no Wilcoxon) ===
    for metric in SYSTEM_METRIC_DIMENSIONS:
        scores1, scores2 = _extract_paired_scores(pairs, metric)

        if scores1 and scores2:
            mean1 = sum(scores1) / len(scores1)
            mean2 = sum(scores2) / len(scores2)
            delta = mean2 - mean1

            comparison["system_metrics"][metric] = {
                "run1_mean": round(mean1, 2),
                "run2_mean": round(mean2, 2),
                "delta": round(delta, 2),
                "n_pairs": len(scores1),
            }
        else:
            comparison["system_metrics"][metric] = {"error": "No valid score pairs"}

    # === Overall Composite Comparison (legacy) ===
    run1_composites = [r1.get("composite_score", 0) for r1, _ in pairs]
    run2_composites = [r2.get("composite_score", 0) for _, r2 in pairs]

    if run1_composites and run2_composites:
        mean1 = sum(run1_composites) / len(run1_composites)
        mean2 = sum(run2_composites) / len(run2_composites)
        delta = mean2 - mean1

        stat, p_value = _wilcoxon_test(run1_composites, run2_composites)
        classification = _classify_change(delta, p_value)

        comparison["overall"] = {
            "run1_mean": round(mean1, 2),
            "run2_mean": round(mean2, 2),
            "delta": round(delta, 2),
            "p_value": round(p_value, 4) if p_value is not None else None,
            "classification": classification,
        }

    # === Per-Dimension Comparison (Script Quality dimensions only) ===
    for dimension in SCRIPT_QUALITY_DIMENSIONS:
        scores1, scores2 = _extract_paired_scores(pairs, dimension)

        if not scores1:
            comparison["by_dimension"][dimension] = {
                "error": "No valid score pairs",
            }
            continue

        mean1 = sum(scores1) / len(scores1)
        mean2 = sum(scores2) / len(scores2)
        delta = mean2 - mean1

        stat, p_value = _wilcoxon_test(scores1, scores2)
        classification = _classify_change(delta, p_value)

        comparison["by_dimension"][dimension] = {
            "run1_mean": round(mean1, 2),
            "run2_mean": round(mean2, 2),
            "delta": round(delta, 2),
            "p_value": round(p_value, 4) if p_value is not None else None,
            "classification": classification,
            "n_pairs": len(scores1),
        }

        if classification == "IMPROVED":
            comparison["improvements"].append(dimension)
        elif classification == "REGRESSION":
            comparison["regressions"].append(dimension)

    # === Feedback Theme Comparison ===
    # Try to load aggregations for theme comparison
    agg1 = _load_aggregation(run1_id)
    agg2 = _load_aggregation(run2_id)

    if agg1 and agg2:
        themes1 = agg1.get("feedback_themes", [])
        themes2 = agg2.get("feedback_themes", [])
        comparison["feedback_theme_diff"] = _diff_feedback_themes(themes1, themes2)

    return comparison


def save_comparison(run1_id: str, run2_id: str, comparison: dict) -> Path:
    """Save comparison result to JSON file."""
    output_path = RUNS_DIR / f"compare_{run1_id}_vs_{run2_id}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2, ensure_ascii=False)
    return output_path
