"""
Report Generation

Generates Markdown reports for evaluation runs and comparisons.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from judge.config import SCRIPT_QUALITY_DIMENSIONS, SYSTEM_METRIC_DIMENSIONS

PROJECT_ROOT = Path(__file__).parent.parent
RUNS_DIR = PROJECT_ROOT / "data" / "runs"

# Dimension display names
DIMENSION_NAMES = {
    "timing_accuracy": "Timing Accuracy",
    "template_compatibility": "Template Compatibility",
    "hook_quality": "Hook Quality",
    "tone_match": "Tone Match",
    "structural_flow": "Structural Flow",
    "content_richness": "Content Richness",
    "completeness": "Completeness",
}

# Script Quality dimensions (LLM-judged, equal weight)
SCRIPT_QUALITY_DIMENSION_NAMES = {
    dim: DIMENSION_NAMES[dim] for dim in SCRIPT_QUALITY_DIMENSIONS
}

# System Metric dimensions (deterministic)
SYSTEM_METRIC_DIMENSION_NAMES = {
    dim: DIMENSION_NAMES[dim] for dim in SYSTEM_METRIC_DIMENSIONS
}


def _load_run_result(run_id: str) -> dict:
    """Load run result from JSON file."""
    run_path = RUNS_DIR / f"{run_id}.json"
    with open(run_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_aggregation(run_id: str) -> Optional[dict]:
    """Load aggregation result if it exists."""
    agg_path = RUNS_DIR / f"{run_id}_aggregation.json"
    if not agg_path.exists():
        return None
    with open(agg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _format_score(score: Optional[float], decimals: int = 2) -> str:
    """Format a score for display."""
    if score is None:
        return "N/A"
    return f"{score:.{decimals}f}"


def _classification_emoji(classification: str) -> str:
    """Get emoji for classification."""
    if classification == "IMPROVED":
        return "IMPROVED"
    elif classification == "REGRESSION":
        return "REGRESSION"
    return ""


def generate_report(
    run_id: str,
    run_result: Optional[dict] = None,
    aggregation: Optional[dict] = None,
) -> str:
    """
    Generate a Markdown report for a single evaluation run.

    Args:
        run_id: The run ID
        run_result: Optional pre-loaded run result
        aggregation: Optional pre-loaded aggregation

    Returns:
        Markdown report string
    """
    # Load data if not provided
    if run_result is None:
        run_result = _load_run_result(run_id)
    if aggregation is None:
        aggregation = _load_aggregation(run_id)

    lines = []

    # === Header ===
    lines.append(f"# Evaluation Report: {run_id}")
    lines.append("")
    lines.append(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    lines.append("")

    # === Summary ===
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Prompt Version:** {run_result.get('prompt_version', 'Unknown')}")
    lines.append(f"- **Prompt Type:** {run_result.get('prompt_type', 'Unknown')}")
    lines.append(f"- **Generation Model:** {run_result.get('generation_model', 'Unknown')}")
    lines.append(f"- **Judge Model:** {run_result.get('judge_model', 'Unknown')} ({run_result.get('judge_provider', '')})")
    lines.append(f"- **Test Inputs:** {run_result.get('test_suite_size', 0)}")
    lines.append(f"- **Successfully Evaluated:** {len(run_result.get('results', []))}")
    lines.append(f"- **Errors:** {len(run_result.get('errors', []))}")
    lines.append(f"- **Duration:** {run_result.get('duration_seconds', 0):.1f} seconds")
    lines.append("")

    # === Script Quality Score ===
    if aggregation and "script_quality" in aggregation:
        sq = aggregation["script_quality"]
        lines.append(f"## Script Quality: {_format_score(sq.get('mean'))} / 5")
        lines.append("")
        lines.append("*Average of 5 LLM-judged dimensions (equal weight)*")
        lines.append("")
        lines.append("| Dimension | Score |")
        lines.append("|-----------|-------|")

        if "by_dimension" in aggregation:
            for dim_key in SCRIPT_QUALITY_DIMENSIONS:
                dim_name = DIMENSION_NAMES.get(dim_key, dim_key)
                dim_stats = aggregation["by_dimension"].get(dim_key, {})
                lines.append(f"| {dim_name} | {_format_score(dim_stats.get('mean'))} |")
        lines.append("")
    else:
        stats = run_result.get("statistics", {})
        lines.append("## Script Quality")
        lines.append("")
        lines.append(f"**Mean Score:** {_format_score(stats.get('script_quality_mean', stats.get('composite_mean')))}")
        lines.append("")

    # === System Metrics ===
    lines.append("## System Metrics")
    lines.append("")
    lines.append("*Deterministic scorers (not part of Script Quality)*")
    lines.append("")
    lines.append("| Metric | Score |")
    lines.append("|--------|-------|")

    if aggregation and "system_metrics" in aggregation:
        sys_metrics = aggregation["system_metrics"]
        timing = sys_metrics.get("timing_accuracy", {})
        template = sys_metrics.get("template_compatibility", {})
        lines.append(f"| Timing Accuracy | {_format_score(timing.get('mean'))} / 5 |")
        lines.append(f"| Template Compatibility | {_format_score(template.get('mean'))} / 5 |")
    elif aggregation and "by_dimension" in aggregation:
        timing_stats = aggregation["by_dimension"].get("timing_accuracy", {})
        template_stats = aggregation["by_dimension"].get("template_compatibility", {})
        lines.append(f"| Timing Accuracy | {_format_score(timing_stats.get('mean'))} / 5 |")
        lines.append(f"| Template Compatibility | {_format_score(template_stats.get('mean'))} / 5 |")
    else:
        lines.append("| Timing Accuracy | N/A |")
        lines.append("| Template Compatibility | N/A |")
    lines.append("")

    # === Legacy Composite Score (hidden detail) ===
    if aggregation and "overall" in aggregation:
        overall = aggregation["overall"]
        lines.append("<details>")
        lines.append("<summary>Legacy Composite Score (all 7 dimensions)</summary>")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Mean | {_format_score(overall.get('mean'))} |")
        lines.append(f"| Median | {_format_score(overall.get('median'))} |")
        lines.append(f"| Std Dev | {_format_score(overall.get('std'))} |")
        lines.append(f"| Min | {_format_score(overall.get('min'))} |")
        lines.append(f"| Max | {_format_score(overall.get('max'))} |")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    # === Breakdown by Video Type ===
    if aggregation and "by_video_type" in aggregation:
        lines.append("## Breakdown by Video Type")
        lines.append("")
        lines.append("| Video Type | Count | Mean | Median | Std |")
        lines.append("|------------|-------|------|--------|-----|")

        for video_type, type_stats in sorted(aggregation["by_video_type"].items()):
            lines.append(
                f"| {video_type} | {type_stats.get('count', 0)} | "
                f"{_format_score(type_stats.get('mean'))} | "
                f"{_format_score(type_stats.get('median'))} | "
                f"{_format_score(type_stats.get('std'))} |"
            )
        lines.append("")

    # === Feedback Themes ===
    if aggregation and "feedback_themes" in aggregation:
        themes = aggregation["feedback_themes"]
        if themes:
            total_evaluated = aggregation.get("total_evaluated", 1)
            lines.append("## Feedback Themes")
            lines.append("")
            lines.append("*Top improvement areas ranked by frequency:*")
            lines.append("")

            for i, theme in enumerate(themes[:10], 1):
                count = theme.get("count", 0)
                pct = (count / total_evaluated) * 100 if total_evaluated > 0 else 0
                affected = ", ".join(theme.get("affected_dimensions", []))

                lines.append(f"### {i}. {theme.get('name', 'Unknown Theme')}")
                lines.append("")
                lines.append(f"- **Occurrences:** {count} ({pct:.0f}% of scripts)")
                if affected:
                    lines.append(f"- **Affects:** {affected}")
                example = theme.get("representative_example", "")
                if example:
                    lines.append(f"- **Example:** \"{example[:100]}{'...' if len(example) > 100 else ''}\"")
                lines.append("")

    # === Cost Estimate ===
    cost = run_result.get("cost_estimate", {})
    if cost:
        lines.append("## Cost Estimate")
        lines.append("")
        lines.append("| Component | Cost |")
        lines.append("|-----------|------|")
        lines.append(f"| Generation | ${cost.get('generation', 0):.2f} |")
        lines.append(f"| Template Classification | ${cost.get('template_classification', 0):.2f} |")
        lines.append(f"| Judge | ${cost.get('judge', 0):.2f} |")
        lines.append(f"| **Total** | **${cost.get('total', 0):.2f}** |")
        lines.append("")

    # === Errors ===
    errors = run_result.get("errors", [])
    if errors:
        lines.append("## Errors")
        lines.append("")
        lines.append(f"*{len(errors)} inputs failed to evaluate:*")
        lines.append("")
        for err in errors[:10]:
            lines.append(f"- `{err.get('input_id', 'unknown')}`: {err.get('error', 'Unknown error')}")
        if len(errors) > 10:
            lines.append(f"- ... and {len(errors) - 10} more")
        lines.append("")

    return "\n".join(lines)


def generate_comparison_report(
    comparison: dict,
) -> str:
    """
    Generate a Markdown report comparing two evaluation runs.

    Args:
        comparison: Comparison result from compare_runs()

    Returns:
        Markdown report string
    """
    lines = []

    run1_id = comparison.get("run1_id", "Unknown")
    run2_id = comparison.get("run2_id", "Unknown")
    run1_prompt = comparison.get("run1_prompt", "Unknown")
    run2_prompt = comparison.get("run2_prompt", "Unknown")

    # === Header ===
    lines.append(f"# Comparison Report")
    lines.append("")
    lines.append(f"**{run1_prompt}** vs **{run2_prompt}**")
    lines.append("")
    lines.append(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    lines.append("")

    # === Summary ===
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Baseline Run:** {run1_id} ({run1_prompt})")
    lines.append(f"- **Comparison Run:** {run2_id} ({run2_prompt})")
    lines.append(f"- **Matched Inputs:** {comparison.get('matched_inputs', 0)}")
    lines.append("")

    # === Script Quality Comparison ===
    script_quality = comparison.get("script_quality", {})
    if script_quality:
        classification = script_quality.get("classification", "NO_CHANGE")
        emoji = _classification_emoji(classification)
        delta = script_quality.get("delta", 0)
        delta_str = f"+{delta:.2f}" if delta >= 0 else f"{delta:.2f}"

        lines.append("## Script Quality Comparison")
        lines.append("")
        lines.append(f"| Metric | {run1_prompt} | {run2_prompt} | Delta | Significance |")
        lines.append("|--------|--------------|--------------|-------|--------------|")
        lines.append(
            f"| **Script Quality** | {_format_score(script_quality.get('run1_mean'))} | "
            f"{_format_score(script_quality.get('run2_mean'))} | "
            f"{delta_str} | {emoji + ' ' if emoji else ''}(p={_format_score(script_quality.get('p_value'), 4)}) |"
        )
        lines.append("")

        if classification == "IMPROVED":
            lines.append(f"> **Result:** Script Quality improved by {delta:.2f} points (statistically significant)")
        elif classification == "REGRESSION":
            lines.append(f"> **Result:** Script Quality regressed by {abs(delta):.2f} points (statistically significant)")
        else:
            lines.append(f"> **Result:** No statistically significant change in Script Quality")
        lines.append("")

    # === Script Quality Dimension Breakdown ===
    lines.append("### Script Quality Dimensions")
    lines.append("")
    lines.append(f"| Dimension | {run1_prompt} | {run2_prompt} | Delta | Status |")
    lines.append("|-----------|--------------|--------------|-------|--------|")

    by_dim = comparison.get("by_dimension", {})
    for dim_key in SCRIPT_QUALITY_DIMENSIONS:
        dim_name = DIMENSION_NAMES.get(dim_key, dim_key)
        dim_data = by_dim.get(dim_key, {})
        if "error" in dim_data:
            lines.append(f"| {dim_name} | - | - | - | Error |")
            continue

        delta = dim_data.get("delta", 0)
        delta_str = f"+{delta:.2f}" if delta >= 0 else f"{delta:.2f}"
        classification = dim_data.get("classification", "NO_CHANGE")
        emoji = _classification_emoji(classification)
        p_value = dim_data.get("p_value")
        p_str = f"p={p_value:.3f}" if p_value else ""

        status = emoji if emoji else "No change"
        if p_str and emoji:
            status = f"{emoji} ({p_str})"

        lines.append(
            f"| {dim_name} | {_format_score(dim_data.get('run1_mean'))} | "
            f"{_format_score(dim_data.get('run2_mean'))} | {delta_str} | {status} |"
        )
    lines.append("")

    # === System Metrics Comparison ===
    sys_metrics = comparison.get("system_metrics", {})
    if sys_metrics:
        lines.append("## System Metrics Comparison")
        lines.append("")
        lines.append("*Simple mean delta (no statistical test)*")
        lines.append("")
        lines.append(f"| Metric | {run1_prompt} | {run2_prompt} | Delta |")
        lines.append("|--------|--------------|--------------|-------|")

        for metric in SYSTEM_METRIC_DIMENSIONS:
            metric_name = DIMENSION_NAMES.get(metric, metric)
            metric_data = sys_metrics.get(metric, {})
            if "error" in metric_data:
                lines.append(f"| {metric_name} | - | - | Error |")
                continue

            delta = metric_data.get("delta", 0)
            delta_str = f"+{delta:.2f}" if delta >= 0 else f"{delta:.2f}"
            lines.append(
                f"| {metric_name} | {_format_score(metric_data.get('run1_mean'))} | "
                f"{_format_score(metric_data.get('run2_mean'))} | {delta_str} |"
            )
        lines.append("")

    # === Improvements and Regressions ===
    improvements = comparison.get("improvements", [])
    regressions = comparison.get("regressions", [])

    if improvements:
        lines.append("### Improvements")
        lines.append("")
        for item in improvements:
            name = DIMENSION_NAMES.get(item, item)
            lines.append(f"- {name}")
        lines.append("")

    if regressions:
        lines.append("### Regressions")
        lines.append("")
        for item in regressions:
            name = DIMENSION_NAMES.get(item, item)
            lines.append(f"- {name}")
        lines.append("")

    # === Feedback Theme Diff ===
    theme_diff = comparison.get("feedback_theme_diff", {})
    if theme_diff:
        resolved = theme_diff.get("resolved", [])
        persistent = theme_diff.get("persistent", [])
        new_themes = theme_diff.get("new", [])

        lines.append("## Feedback Theme Changes")
        lines.append("")

        if resolved:
            lines.append("### Resolved Themes")
            lines.append("")
            lines.append("*These issues appeared in the baseline but not in the new version:*")
            lines.append("")
            for theme in resolved:
                lines.append(f"- **{theme.get('name', 'Unknown')}** (was {theme.get('count', 0)} occurrences)")
            lines.append("")

        if new_themes:
            lines.append("### New Themes")
            lines.append("")
            lines.append("*These issues appeared in the new version but not in the baseline:*")
            lines.append("")
            for theme in new_themes:
                lines.append(f"- **{theme.get('name', 'Unknown')}** ({theme.get('count', 0)} occurrences)")
            lines.append("")

        if persistent:
            lines.append("### Persistent Themes")
            lines.append("")
            lines.append("*These issues appear in both versions:*")
            lines.append("")
            lines.append("| Theme | Baseline | New | Change |")
            lines.append("|-------|----------|-----|--------|")
            for theme in persistent:
                c1 = theme.get("run1_count", 0)
                c2 = theme.get("run2_count", 0)
                change = c2 - c1
                change_str = f"+{change}" if change >= 0 else str(change)
                lines.append(f"| {theme.get('name', 'Unknown')} | {c1} | {c2} | {change_str} |")
            lines.append("")

    return "\n".join(lines)


def save_report(run_id: str, report: str) -> Path:
    """Save report to Markdown file."""
    output_path = RUNS_DIR / f"{run_id}_report.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    return output_path


def save_comparison_report(run1_id: str, run2_id: str, report: str) -> Path:
    """Save comparison report to Markdown file."""
    output_path = RUNS_DIR / f"compare_{run1_id}_vs_{run2_id}_report.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    return output_path
