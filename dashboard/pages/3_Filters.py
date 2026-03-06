"""
Filters Page

Analyze results by video type, duration, and platform.
"""

import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Filters - Eval-Judge",
    page_icon="🔍",
    layout="wide",
)

from dashboard.data.loader import list_runs, load_run
from dashboard.components.charts import scatter_plot, breakdown_bar_chart
from dashboard.config import VIDEO_TYPES, DURATION_RANGES, PLATFORMS


def main():
    st.title("🔍 Filter & Analyze")

    # Get available runs
    runs = list_runs()

    if not runs:
        st.warning("No evaluation runs found.")
        return

    # Sidebar filters
    st.sidebar.header("Filters")

    # Run selector
    run_options = {
        f"{r['prompt_version']} ({r['run_id'][:20]}...)": r['run_id']
        for r in runs
    }

    selected_label = st.sidebar.selectbox(
        "Select Run",
        options=list(run_options.keys()),
        index=0,
    )
    selected_run_id = run_options[selected_label]

    # Load run data
    run_data = load_run(selected_run_id)

    if not run_data:
        st.error("Failed to load run data.")
        return

    results = run_data.get("results", [])

    if not results:
        st.warning("No results in this run.")
        return

    # Build DataFrame from results
    rows = []
    for r in results:
        test_input = r.get("test_input", {})
        scores = r.get("scores", {})

        rows.append({
            "script_id": r.get("script_id", "")[:8],
            "video_type": test_input.get("video_type", "Unknown"),
            "subject": test_input.get("subject", "")[:50],
            "duration_range": test_input.get("duration_range", "Unknown"),
            "platform": test_input.get("platform") or "Unknown",
            "script_quality": r.get("script_quality_score", 0),
            "timing_accuracy": scores.get("timing_accuracy", {}).get("score", 0),
            "template_compatibility": scores.get("template_compatibility", {}).get("score", 0),
            "hook_quality": scores.get("hook_quality", {}).get("score", 0),
            "tone_match": scores.get("tone_match", {}).get("score", 0),
            "structural_flow": scores.get("structural_flow", {}).get("score", 0),
            "content_richness": scores.get("content_richness", {}).get("score", 0),
            "completeness": scores.get("completeness", {}).get("score", 0),
            "word_count": r.get("word_count", 0),
            "estimated_time_sec": r.get("estimated_time_sec", 0),
        })

    df = pd.DataFrame(rows)

    # Filter widgets
    available_types = df["video_type"].unique().tolist()
    available_durations = df["duration_range"].unique().tolist()
    available_platforms = df["platform"].unique().tolist()

    selected_types = st.sidebar.multiselect(
        "Video Type",
        options=available_types,
        default=available_types,
    )

    selected_durations = st.sidebar.multiselect(
        "Duration Range",
        options=available_durations,
        default=available_durations,
    )

    selected_platforms = st.sidebar.multiselect(
        "Platform",
        options=available_platforms,
        default=available_platforms,
    )

    # Apply filters
    filtered_df = df[
        (df["video_type"].isin(selected_types)) &
        (df["duration_range"].isin(selected_durations)) &
        (df["platform"].isin(selected_platforms))
    ]

    # Summary stats
    st.subheader("Filtered Results")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Scripts", len(filtered_df))
    with col2:
        st.metric("Avg Script Quality", f"{filtered_df['script_quality'].mean():.2f}" if len(filtered_df) > 0 else "N/A")
    with col3:
        st.metric("Avg Timing", f"{filtered_df['timing_accuracy'].mean():.2f}" if len(filtered_df) > 0 else "N/A")
    with col4:
        st.metric("Avg Template", f"{filtered_df['template_compatibility'].mean():.2f}" if len(filtered_df) > 0 else "N/A")

    st.divider()

    # Scatter plot
    st.subheader("Duration vs Quality")

    if len(filtered_df) > 0:
        fig = scatter_plot(
            filtered_df,
            x="estimated_time_sec",
            y="script_quality",
            color="video_type",
            title="Estimated Duration vs Script Quality",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data to display.")

    st.divider()

    # Breakdown charts
    st.subheader("Breakdowns")

    tab1, tab2, tab3 = st.tabs(["By Video Type", "By Duration", "By Platform"])

    with tab1:
        if len(filtered_df) > 0:
            type_breakdown = filtered_df.groupby("video_type").agg({
                "script_quality": ["mean", "count", "std"],
            }).round(2)
            type_breakdown.columns = ["mean", "count", "std"]
            type_breakdown = type_breakdown.reset_index()

            breakdown_dict = {
                row["video_type"]: {
                    "mean": row["mean"],
                    "count": row["count"],
                    "std": row["std"],
                }
                for _, row in type_breakdown.iterrows()
            }

            fig = breakdown_bar_chart(breakdown_dict, title="Script Quality by Video Type")
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(type_breakdown, use_container_width=True, hide_index=True)

    with tab2:
        if len(filtered_df) > 0:
            duration_breakdown = filtered_df.groupby("duration_range").agg({
                "script_quality": ["mean", "count", "std"],
            }).round(2)
            duration_breakdown.columns = ["mean", "count", "std"]
            duration_breakdown = duration_breakdown.reset_index()

            breakdown_dict = {
                row["duration_range"]: {
                    "mean": row["mean"],
                    "count": row["count"],
                    "std": row["std"],
                }
                for _, row in duration_breakdown.iterrows()
            }

            fig = breakdown_bar_chart(breakdown_dict, title="Script Quality by Duration")
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(duration_breakdown, use_container_width=True, hide_index=True)

    with tab3:
        if len(filtered_df) > 0:
            platform_breakdown = filtered_df.groupby("platform").agg({
                "script_quality": ["mean", "count", "std"],
            }).round(2)
            platform_breakdown.columns = ["mean", "count", "std"]
            platform_breakdown = platform_breakdown.reset_index()

            breakdown_dict = {
                row["platform"]: {
                    "mean": row["mean"],
                    "count": row["count"],
                    "std": row["std"],
                }
                for _, row in platform_breakdown.iterrows()
            }

            fig = breakdown_bar_chart(breakdown_dict, title="Script Quality by Platform")
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(platform_breakdown, use_container_width=True, hide_index=True)

    st.divider()

    # Data table
    st.subheader("Filtered Data")

    display_cols = [
        "script_id", "video_type", "duration_range", "platform",
        "script_quality", "timing_accuracy", "template_compatibility",
    ]

    st.dataframe(
        filtered_df[display_cols].sort_values("script_quality", ascending=False),
        use_container_width=True,
        hide_index=True,
    )


if __name__ == "__main__":
    main()
