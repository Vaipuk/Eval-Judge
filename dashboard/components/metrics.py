"""Metric display components."""

import streamlit as st
from typing import Optional

from dashboard.config import CLASSIFICATION_COLORS


def score_card(
    label: str,
    value: float,
    delta: Optional[float] = None,
    max_value: float = 5.0,
    help_text: Optional[str] = None,
):
    """
    Display a score metric card.

    Args:
        label: Metric label
        value: Score value
        delta: Optional delta from previous
        max_value: Maximum possible value
        help_text: Optional help tooltip
    """
    delta_str = None
    delta_color = "normal"

    if delta is not None:
        delta_str = f"{delta:+.2f}"
        delta_color = "normal" if delta >= 0 else "inverse"

    st.metric(
        label=label,
        value=f"{value:.2f} / {max_value:.0f}",
        delta=delta_str,
        delta_color=delta_color,
        help=help_text,
    )


def delta_badge(delta: float, show_value: bool = True) -> str:
    """
    Create an HTML badge showing delta with color.

    Args:
        delta: The delta value
        show_value: Whether to show the numeric value

    Returns:
        HTML string for the badge
    """
    if delta > 0:
        color = CLASSIFICATION_COLORS["IMPROVED"]
        symbol = "+"
    elif delta < 0:
        color = CLASSIFICATION_COLORS["REGRESSION"]
        symbol = ""
    else:
        color = CLASSIFICATION_COLORS["NO_CHANGE"]
        symbol = ""

    if show_value:
        text = f"{symbol}{delta:.2f}"
    else:
        text = "+" if delta > 0 else ("-" if delta < 0 else "=")

    return f'<span style="background-color: {color}; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold;">{text}</span>'


def classification_badge(classification: str) -> str:
    """
    Create an HTML badge for classification status.

    Args:
        classification: IMPROVED, REGRESSION, or NO_CHANGE

    Returns:
        HTML string for the badge
    """
    color = CLASSIFICATION_COLORS.get(classification, "#95A5A6")

    labels = {
        "IMPROVED": "Improved",
        "REGRESSION": "Regression",
        "NO_CHANGE": "No Change",
    }
    label = labels.get(classification, classification)

    return f'<span style="background-color: {color}; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 14px;">{label}</span>'


def stat_row(stats: dict, prefix: str = ""):
    """
    Display a row of statistics.

    Args:
        stats: Dict with mean, median, std, min, max, count
        prefix: Optional prefix for column keys
    """
    cols = st.columns(5)

    with cols[0]:
        st.metric("Mean", f"{stats.get('mean', 0):.2f}")
    with cols[1]:
        st.metric("Median", f"{stats.get('median', 0):.2f}")
    with cols[2]:
        st.metric("Std Dev", f"{stats.get('std', 0):.2f}")
    with cols[3]:
        st.metric("Min", f"{stats.get('min', 0):.1f}")
    with cols[4]:
        st.metric("Max", f"{stats.get('max', 0):.1f}")
