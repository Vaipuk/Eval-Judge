"""
Trends Page

Track score trends over time across evaluation runs.
"""

import streamlit as st
import plotly.graph_objects as go

st.set_page_config(
    page_title="Trends - Eval-Judge",
    page_icon="📉",
    layout="wide",
)

from dashboard.data.loader import list_runs, load_aggregation
from dashboard.config import DIMENSION_NAMES, SCRIPT_QUALITY_DIMENSIONS, SYSTEM_METRIC_DIMENSIONS


def main():
    st.title("📉 Historical Trends")

    # Get all runs
    runs = list_runs()

    if len(runs) < 2:
        st.info("Need at least 2 runs to show trends.")
        return

    # Sort by timestamp ascending for trend display
    runs_sorted = sorted(runs, key=lambda x: x["timestamp"])

    # Collect data points
    data_points = []

    for run in runs_sorted:
        agg = load_aggregation(run["run_id"])

        point = {
            "run_id": run["run_id"],
            "prompt_version": run["prompt_version"],
            "timestamp": run["timestamp"][:10],  # Date only
            "full_timestamp": run["timestamp"],
        }

        if agg:
            # Script quality
            sq = agg.get("script_quality", {})
            point["script_quality"] = sq.get("mean", 0)

            # System metrics
            sys_metrics = agg.get("system_metrics", {})
            point["timing_accuracy"] = sys_metrics.get("timing_accuracy", {}).get("mean", 0)
            point["template_compatibility"] = sys_metrics.get("template_compatibility", {}).get("mean", 0)

            # Individual dimensions
            by_dim = agg.get("by_dimension", {})
            for dim in SCRIPT_QUALITY_DIMENSIONS:
                point[dim] = by_dim.get(dim, {}).get("mean", 0)
        else:
            # Use statistics from run metadata
            stats = run.get("statistics", {})
            point["script_quality"] = stats.get("script_quality_mean", 0)

        data_points.append(point)

    if not data_points:
        st.warning("No aggregation data available for trend analysis.")
        return

    # Main trend chart
    st.subheader("Script Quality Over Time")

    x_values = [p["timestamp"] for p in data_points]
    y_values = [p.get("script_quality", 0) for p in data_points]
    labels = [p["prompt_version"] for p in data_points]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=x_values,
        y=y_values,
        mode='lines+markers',
        name='Script Quality',
        line=dict(color='#3498DB', width=3),
        marker=dict(size=10),
        text=labels,
        hovertemplate="<b>%{text}</b><br>Score: %{y:.2f}<br>%{x}<extra></extra>",
    ))

    # Add annotations for prompt versions
    for i, point in enumerate(data_points):
        fig.add_annotation(
            x=point["timestamp"],
            y=point.get("script_quality", 0),
            text=point["prompt_version"],
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1,
            ax=0,
            ay=-40,
            font=dict(size=10),
        )

    fig.update_layout(
        yaxis=dict(range=[0, 5], title="Score"),
        xaxis=dict(title="Date"),
        height=400,
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Dimension selector
    st.subheader("Dimension Trends")

    dimension_options = {
        "Script Quality": "script_quality",
        **{DIMENSION_NAMES[d]: d for d in SCRIPT_QUALITY_DIMENSIONS},
        "Timing Accuracy": "timing_accuracy",
        "Template Compatibility": "template_compatibility",
    }

    selected_dimensions = st.multiselect(
        "Select dimensions to compare",
        options=list(dimension_options.keys()),
        default=["Script Quality", "Hook Quality", "Content Richness"],
    )

    if selected_dimensions:
        fig = go.Figure()

        colors = ['#3498DB', '#E74C3C', '#2ECC71', '#F39C12', '#9B59B6', '#1ABC9C', '#34495E']

        for i, dim_label in enumerate(selected_dimensions):
            dim_key = dimension_options[dim_label]
            y_vals = [p.get(dim_key, 0) for p in data_points]

            fig.add_trace(go.Scatter(
                x=x_values,
                y=y_vals,
                mode='lines+markers',
                name=dim_label,
                line=dict(color=colors[i % len(colors)], width=2),
                marker=dict(size=8),
            ))

        fig.update_layout(
            yaxis=dict(range=[0, 5], title="Score"),
            xaxis=dict(title="Date"),
            height=400,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )

        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Run timeline table
    st.subheader("Run Timeline")

    import pandas as pd

    timeline_data = []
    for point in data_points:
        timeline_data.append({
            "Date": point["timestamp"],
            "Prompt": point["prompt_version"],
            "Script Quality": f"{point.get('script_quality', 0):.2f}",
            "Timing": f"{point.get('timing_accuracy', 0):.2f}",
            "Template": f"{point.get('template_compatibility', 0):.2f}",
        })

    df = pd.DataFrame(timeline_data)
    st.dataframe(df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
