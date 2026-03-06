"""Table components."""

import streamlit as st
import pandas as pd
from typing import Optional

from dashboard.config import DIMENSION_NAMES, SCRIPT_QUALITY_DIMENSIONS, SYSTEM_METRIC_DIMENSIONS


def dimension_scores_table(
    scores: dict,
    show_all: bool = True,
):
    """
    Display a table of dimension scores.

    Args:
        scores: Dict mapping dimension to score data
        show_all: If True, show all dimensions; if False, only script quality
    """
    dimensions = (SCRIPT_QUALITY_DIMENSIONS + SYSTEM_METRIC_DIMENSIONS) if show_all else SCRIPT_QUALITY_DIMENSIONS

    rows = []
    for dim in dimensions:
        dim_data = scores.get(dim, {})

        if isinstance(dim_data, dict):
            score = dim_data.get("score") or dim_data.get("mean", "N/A")
            if isinstance(score, (int, float)):
                score = f"{score:.2f}" if isinstance(score, float) else str(score)
        else:
            score = str(dim_data) if dim_data else "N/A"

        rows.append({
            "Dimension": DIMENSION_NAMES.get(dim, dim),
            "Score": score,
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", hide_index=True)


def feedback_themes_table(themes: list[dict]):
    """
    Display a table of feedback themes.

    Args:
        themes: List of theme dicts with name, count, representative_example
    """
    if not themes:
        st.info("No feedback themes available.")
        return

    rows = []
    for i, theme in enumerate(themes, 1):
        rows.append({
            "Rank": i,
            "Theme": theme.get("name", "Unknown")[:50] + "..." if len(theme.get("name", "")) > 50 else theme.get("name", "Unknown"),
            "Count": theme.get("count", 0),
            "Example": theme.get("representative_example", "")[:60] + "..." if len(theme.get("representative_example", "")) > 60 else theme.get("representative_example", ""),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", hide_index=True)


def comparison_table(
    comparison: dict,
    dimensions: Optional[list] = None,
):
    """
    Display a comparison table with deltas and significance.

    Args:
        comparison: Comparison dict from compare module
        dimensions: List of dimensions to show
    """
    if dimensions is None:
        dimensions = SCRIPT_QUALITY_DIMENSIONS

    by_dim = comparison.get("by_dimension", {})

    rows = []
    for dim in dimensions:
        dim_data = by_dim.get(dim, {})

        if "error" in dim_data:
            rows.append({
                "Dimension": DIMENSION_NAMES.get(dim, dim),
                "Baseline": "-",
                "Comparison": "-",
                "Delta": "-",
                "p-value": "-",
                "Status": "Error",
            })
            continue

        run1_mean = dim_data.get("run1_mean", 0)
        run2_mean = dim_data.get("run2_mean", 0)
        delta = dim_data.get("delta", 0)
        p_value = dim_data.get("p_value")
        classification = dim_data.get("classification", "NO_CHANGE")

        rows.append({
            "Dimension": DIMENSION_NAMES.get(dim, dim),
            "Baseline": f"{run1_mean:.2f}",
            "Comparison": f"{run2_mean:.2f}",
            "Delta": f"{delta:+.2f}",
            "p-value": f"{p_value:.4f}" if p_value else "N/A",
            "Status": classification,
        })

    df = pd.DataFrame(rows)

    # Apply styling
    def style_status(val):
        if val == "IMPROVED":
            return "background-color: #2ECC71; color: white"
        elif val == "REGRESSION":
            return "background-color: #E74C3C; color: white"
        return ""

    styled_df = df.style.map(style_status, subset=["Status"])
    st.dataframe(styled_df, width="stretch", hide_index=True)


def script_results_table(results: list[dict], max_rows: int = 20):
    """
    Display a table of individual script results.

    Args:
        results: List of result dicts
        max_rows: Maximum rows to show
    """
    if not results:
        st.info("No results available.")
        return

    rows = []
    for r in results[:max_rows]:
        test_input = r.get("test_input", {})
        rows.append({
            "ID": r.get("script_id", "")[:8] + "...",
            "Video Type": test_input.get("video_type", "Unknown"),
            "Subject": (test_input.get("subject", "")[:40] + "...") if len(test_input.get("subject", "")) > 40 else test_input.get("subject", ""),
            "Script Quality": f"{r.get('script_quality_score', 0):.2f}",
            "Timing": r.get("scores", {}).get("timing_accuracy", {}).get("score", "N/A"),
            "Template": r.get("scores", {}).get("template_compatibility", {}).get("score", "N/A"),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", hide_index=True)
