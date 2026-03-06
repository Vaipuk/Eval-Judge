"""
Score Aggregation and Feedback Theme Clustering

Takes evaluation run results and computes:
- Overall aggregate scores (mean, median, std, min, max)
- Breakdowns by video_type, duration_range, platform
- Feedback theme clustering using LLM
"""

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from judge.config import (
    get_judge_client,
    BaseJudge,
    SCRIPT_QUALITY_DIMENSIONS,
    SYSTEM_METRIC_DIMENSIONS,
)

PROJECT_ROOT = Path(__file__).parent.parent
RUNS_DIR = PROJECT_ROOT / "data" / "runs"

# All scoring dimensions (for backward compatibility)
DIMENSIONS = SCRIPT_QUALITY_DIMENSIONS + SYSTEM_METRIC_DIMENSIONS


def _load_run_result(run_id: str) -> dict:
    """Load a run result from JSON file."""
    run_path = RUNS_DIR / f"{run_id}.json"
    if not run_path.exists():
        raise FileNotFoundError(f"Run result not found: {run_path}")

    with open(run_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _compute_dimension_stats(scores: list[Optional[int]]) -> dict:
    """Compute statistics for a list of scores."""
    # Filter out None values
    valid_scores = [s for s in scores if s is not None]

    if not valid_scores:
        return {
            "mean": None,
            "median": None,
            "std": None,
            "min": None,
            "max": None,
            "count": 0,
            "missing": len(scores),
        }

    return {
        "mean": round(statistics.mean(valid_scores), 2),
        "median": round(statistics.median(valid_scores), 2),
        "std": round(statistics.stdev(valid_scores), 2) if len(valid_scores) > 1 else 0.0,
        "min": min(valid_scores),
        "max": max(valid_scores),
        "count": len(valid_scores),
        "missing": len(scores) - len(valid_scores),
    }


def _extract_dimension_scores(results: list[dict], dimension: str) -> list[Optional[int]]:
    """Extract scores for a dimension from all results."""
    scores = []
    for r in results:
        dim_data = r.get("scores", {}).get(dimension, {})
        score = dim_data.get("score")
        scores.append(score)
    return scores


def _cluster_feedback_with_llm(
    improvements: list[str],
    judge: BaseJudge,
    max_themes: int = 10,
) -> list[dict]:
    """
    Use LLM to cluster improvements into themes.

    Returns list of themes with:
    - name: Short theme name
    - count: Number of occurrences
    - affected_dimensions: Which dimensions this relates to
    - representative_example: One example improvement
    - improvements: All improvements in this theme
    """
    if not improvements:
        return []

    # Build prompt for clustering
    system_prompt = """You are an analysis assistant. Your task is to cluster a list of improvement suggestions into meaningful themes.

Each theme should:
1. Group similar suggestions together
2. Have a short, descriptive name (5-10 words max)
3. Identify which scoring dimensions it affects (timing_accuracy, template_compatibility, hook_quality, tone_match, structural_flow, content_richness, completeness)

Output valid JSON only."""

    # Deduplicate and count improvements
    improvement_counts = Counter(improvements)
    unique_improvements = list(improvement_counts.keys())

    # Limit to avoid context overflow
    if len(unique_improvements) > 100:
        # Keep most frequent
        unique_improvements = [imp for imp, _ in improvement_counts.most_common(100)]

    user_prompt = f"""Cluster the following {len(unique_improvements)} unique improvement suggestions into {max_themes} or fewer themes.

IMPROVEMENTS:
{json.dumps(unique_improvements, indent=2)}

OCCURRENCE COUNTS:
{json.dumps(dict(improvement_counts.most_common(50)), indent=2)}

Return a JSON object with this structure:
{{
  "themes": [
    {{
      "name": "Theme name",
      "count": <total occurrences of all improvements in this theme>,
      "affected_dimensions": ["dimension1", "dimension2"],
      "representative_example": "One example improvement from this theme",
      "improvement_indices": [0, 3, 7]  // indices into the IMPROVEMENTS list
    }}
  ]
}}

Rank themes by count (most frequent first)."""

    try:
        response = judge.evaluate(system_prompt, user_prompt)
        themes_data = response.get("themes", [])

        # Enrich with actual improvements
        for theme in themes_data:
            indices = theme.get("improvement_indices", [])
            theme["improvements"] = [
                unique_improvements[i] for i in indices
                if i < len(unique_improvements)
            ]
            # Recalculate count based on actual occurrences
            theme["count"] = sum(
                improvement_counts.get(imp, 0) for imp in theme["improvements"]
            )
            # Remove indices from output
            theme.pop("improvement_indices", None)

        # Sort by count
        themes_data.sort(key=lambda x: x.get("count", 0), reverse=True)

        return themes_data[:max_themes]

    except Exception as e:
        # Fallback: simple frequency-based grouping
        print(f"[WARN] LLM clustering failed: {e}. Using fallback.")
        return _fallback_clustering(improvements, max_themes)


def _fallback_clustering(improvements: list[str], max_themes: int) -> list[dict]:
    """Simple fallback clustering based on keyword frequency."""
    improvement_counts = Counter(improvements)

    themes = []
    for improvement, count in improvement_counts.most_common(max_themes):
        themes.append({
            "name": improvement[:50] + "..." if len(improvement) > 50 else improvement,
            "count": count,
            "affected_dimensions": [],
            "representative_example": improvement,
            "improvements": [improvement],
        })

    return themes


def aggregate_run(
    run_id: str,
    run_result: Optional[dict] = None,
    cluster_feedback: bool = True,
) -> dict:
    """
    Aggregate scores and cluster feedback for an evaluation run.

    Args:
        run_id: The run ID to aggregate
        run_result: Optional pre-loaded run result (skips file load)
        cluster_feedback: Whether to use LLM to cluster feedback themes

    Returns:
        Aggregation result with overall stats, breakdowns, and themes
    """
    # Load run result if not provided
    if run_result is None:
        run_result = _load_run_result(run_id)

    results = run_result.get("results", [])
    if not results:
        return {"error": "No results to aggregate"}

    aggregation = {
        "run_id": run_id,
        "prompt_version": run_result.get("prompt_version"),
        "total_evaluated": len(results),
        # New structure: separate script quality from system metrics
        "script_quality": {},  # Average of 5 LLM-judged dimensions
        "system_metrics": {    # Standalone deterministic metrics
            "timing_accuracy": {},
            "template_compatibility": {},
        },
        "overall": {},  # Legacy: weighted composite of all 7
        "by_dimension": {},
        "by_video_type": {},
        "by_duration_range": {},
        "by_platform": {},
        "feedback_themes": [],
    }

    # === Script Quality (average of 5 LLM dimensions) ===
    script_quality_scores = [r.get("script_quality_score") for r in results]
    aggregation["script_quality"] = _compute_dimension_stats(script_quality_scores)

    # === System Metrics (standalone) ===
    timing_scores = _extract_dimension_scores(results, "timing_accuracy")
    template_scores = _extract_dimension_scores(results, "template_compatibility")
    aggregation["system_metrics"]["timing_accuracy"] = _compute_dimension_stats(timing_scores)
    aggregation["system_metrics"]["template_compatibility"] = _compute_dimension_stats(template_scores)

    # === Overall Composite Scores (legacy, all 7 dimensions) ===
    composites = [r.get("composite_score") for r in results]
    aggregation["overall"] = _compute_dimension_stats(composites)

    # === Per-Dimension Stats ===
    for dimension in DIMENSIONS:
        scores = _extract_dimension_scores(results, dimension)
        aggregation["by_dimension"][dimension] = _compute_dimension_stats(scores)

    # === Breakdown by Video Type (using script_quality_score) ===
    by_type = defaultdict(list)
    for r in results:
        video_type = r.get("metadata", {}).get("video_type", "Unknown")
        by_type[video_type].append(r.get("script_quality_score"))

    for video_type, scores in by_type.items():
        aggregation["by_video_type"][video_type] = _compute_dimension_stats(scores)

    # === Breakdown by Duration Range (using script_quality_score) ===
    by_duration = defaultdict(list)
    for r in results:
        duration_range = r.get("test_input", {}).get("duration_range") or "Unknown"
        by_duration[duration_range].append(r.get("script_quality_score"))

    for duration_range, scores in by_duration.items():
        aggregation["by_duration_range"][duration_range] = _compute_dimension_stats(scores)

    # === Breakdown by Platform (using script_quality_score) ===
    by_platform = defaultdict(list)
    for r in results:
        platform = r.get("metadata", {}).get("platform") or "Unknown"
        by_platform[platform].append(r.get("script_quality_score"))

    for platform, scores in by_platform.items():
        aggregation["by_platform"][platform] = _compute_dimension_stats(scores)

    # === Feedback Theme Clustering ===
    if cluster_feedback:
        # Collect all improvements
        all_improvements = []
        for r in results:
            all_improvements.extend(r.get("all_improvements", []))

        if all_improvements:
            judge = get_judge_client()
            aggregation["feedback_themes"] = _cluster_feedback_with_llm(
                all_improvements, judge, max_themes=10
            )

    return aggregation


def save_aggregation(run_id: str, aggregation: dict) -> Path:
    """Save aggregation result to JSON file."""
    output_path = RUNS_DIR / f"{run_id}_aggregation.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(aggregation, f, indent=2, ensure_ascii=False)
    return output_path
