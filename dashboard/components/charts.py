"""Chart components using Plotly."""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from typing import Optional

from dashboard.config import (
    DIMENSION_NAMES,
    ALL_DIMENSIONS,
    SCRIPT_QUALITY_DIMENSIONS,
    CLASSIFICATION_COLORS,
)


def radar_chart(
    scores: dict,
    title: str = "Dimension Scores",
    show_all: bool = True,
) -> go.Figure:
    """
    Create a radar chart for dimension scores.

    Args:
        scores: Dict mapping dimension names to scores (1-5)
        title: Chart title
        show_all: If True, show all 7 dimensions; if False, only script quality

    Returns:
        Plotly Figure
    """
    dimensions = ALL_DIMENSIONS if show_all else SCRIPT_QUALITY_DIMENSIONS

    # Extract scores in order
    values = []
    labels = []
    for dim in dimensions:
        dim_data = scores.get(dim, {})
        if isinstance(dim_data, dict):
            score = dim_data.get("score") or dim_data.get("mean", 0)
        else:
            score = dim_data or 0
        values.append(score if score else 0)
        labels.append(DIMENSION_NAMES.get(dim, dim))

    # Close the polygon
    values.append(values[0])
    labels.append(labels[0])

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=labels,
        fill='toself',
        name='Scores',
        line_color='#3498DB',
        fillcolor='rgba(52, 152, 219, 0.3)',
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 5],
                tickvals=[1, 2, 3, 4, 5],
            ),
        ),
        showlegend=False,
        title=dict(text=title, x=0.5),
        height=400,
        margin=dict(l=80, r=80, t=60, b=40),
    )

    return fig


def bar_chart_comparison(
    run1_scores: dict,
    run2_scores: dict,
    run1_label: str = "Baseline",
    run2_label: str = "Comparison",
    dimensions: Optional[list] = None,
) -> go.Figure:
    """
    Create a grouped bar chart comparing two runs.

    Args:
        run1_scores: Dict mapping dimension to score for run 1
        run2_scores: Dict mapping dimension to score for run 2
        run1_label: Label for run 1
        run2_label: Label for run 2
        dimensions: List of dimensions to show (default: all)

    Returns:
        Plotly Figure
    """
    if dimensions is None:
        dimensions = ALL_DIMENSIONS

    labels = [DIMENSION_NAMES.get(d, d) for d in dimensions]

    def get_score(scores_dict: dict, dim: str) -> float:
        data = scores_dict.get(dim, {})
        if isinstance(data, dict):
            return data.get("score") or data.get("mean") or data.get("run1_mean", 0)
        return data or 0

    run1_values = [get_score(run1_scores, d) for d in dimensions]
    run2_values = [get_score(run2_scores, d) for d in dimensions]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name=run1_label,
        x=labels,
        y=run1_values,
        marker_color='#95A5A6',
    ))

    fig.add_trace(go.Bar(
        name=run2_label,
        x=labels,
        y=run2_values,
        marker_color='#3498DB',
    ))

    fig.update_layout(
        barmode='group',
        yaxis=dict(range=[0, 5], title="Score"),
        xaxis=dict(title="Dimension"),
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return fig


def scatter_plot(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: Optional[str] = None,
    title: str = "",
) -> go.Figure:
    """
    Create a scatter plot.

    Args:
        df: DataFrame with data
        x: Column name for x-axis
        y: Column name for y-axis
        color: Column name for color encoding
        title: Chart title

    Returns:
        Plotly Figure
    """
    fig = px.scatter(
        df,
        x=x,
        y=y,
        color=color,
        title=title,
        height=400,
    )

    fig.update_layout(
        xaxis_title=x.replace("_", " ").title(),
        yaxis_title=y.replace("_", " ").title(),
    )

    return fig


def line_chart_trend(
    data: list[dict],
    x_key: str = "timestamp",
    y_key: str = "script_quality_mean",
    title: str = "Score Trend",
) -> go.Figure:
    """
    Create a line chart showing trends over time.

    Args:
        data: List of dicts with timestamp and score data
        x_key: Key for x-axis values
        y_key: Key for y-axis values
        title: Chart title

    Returns:
        Plotly Figure
    """
    if not data:
        fig = go.Figure()
        fig.add_annotation(text="No data available", x=0.5, y=0.5, showarrow=False)
        return fig

    x_values = [d.get(x_key, "") for d in data]
    y_values = [d.get(y_key, 0) or d.get("statistics", {}).get("script_quality_mean", 0) for d in data]
    labels = [d.get("prompt_version", "") for d in data]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=x_values,
        y=y_values,
        mode='lines+markers',
        name='Script Quality',
        line_color='#3498DB',
        text=labels,
        hovertemplate="<b>%{text}</b><br>Score: %{y:.2f}<br>%{x}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text=title, x=0.5),
        yaxis=dict(range=[0, 5], title="Score"),
        xaxis=dict(title=""),
        height=400,
    )

    return fig


def breakdown_bar_chart(
    breakdown_data: dict,
    title: str = "Breakdown",
    metric: str = "mean",
) -> go.Figure:
    """
    Create a bar chart from breakdown data (by_video_type, by_duration, etc).

    Args:
        breakdown_data: Dict mapping category to stats dict
        title: Chart title
        metric: Which metric to display (mean, median, count)

    Returns:
        Plotly Figure
    """
    if not breakdown_data:
        fig = go.Figure()
        fig.add_annotation(text="No data available", x=0.5, y=0.5, showarrow=False)
        return fig

    categories = list(breakdown_data.keys())
    values = [breakdown_data[c].get(metric, 0) for c in categories]
    counts = [breakdown_data[c].get("count", 0) for c in categories]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=categories,
        y=values,
        text=[f"n={c}" for c in counts],
        textposition='outside',
        marker_color='#3498DB',
    ))

    fig.update_layout(
        title=dict(text=title, x=0.5),
        yaxis=dict(range=[0, 5], title="Score"),
        xaxis=dict(title=""),
        height=350,
    )

    return fig
