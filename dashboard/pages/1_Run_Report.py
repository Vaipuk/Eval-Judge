"""
Run Report Page

View detailed results for a single evaluation run.
"""

import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

st.set_page_config(
    page_title="Run Report - Eval-Judge",
    page_icon="📈",
    layout="wide",
)

from dashboard.data.loader import list_runs, load_run, load_aggregation
from dashboard.components.charts import radar_chart, breakdown_bar_chart
from dashboard.components.metrics import score_card, stat_row
from dashboard.components.tables import (
    dimension_scores_table,
    feedback_themes_table,
    script_results_table,
)
from dashboard.config import DIMENSION_NAMES, SCRIPT_QUALITY_DIMENSIONS


def main():
    st.title("📈 Run Report")

    # Get available runs
    runs = list_runs()

    if not runs:
        st.warning("No evaluation runs found.")
        return

    # Run selector
    run_options = {
        f"{r['prompt_version']} ({r['timestamp'][:16]})": r['run_id']
        for r in runs
    }

    selected_label = st.selectbox(
        "Select Run",
        options=list(run_options.keys()),
        index=0,
    )
    selected_run_id = run_options[selected_label]

    # Load data
    run_data = load_run(selected_run_id)
    aggregation = load_aggregation(selected_run_id)

    if not run_data:
        st.error(f"Failed to load run: {selected_run_id}")
        return

    # Run metadata
    with st.expander("Run Details", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Run ID:** {run_data.get('run_id', 'N/A')}")
            st.write(f"**Prompt Version:** {run_data.get('prompt_version', 'N/A')}")
            st.write(f"**Timestamp:** {run_data.get('timestamp', 'N/A')}")
        with col2:
            st.write(f"**Generation Model:** {run_data.get('generation_model', 'N/A')}")
            st.write(f"**Judge Model:** {run_data.get('judge_model', 'N/A')}")
            st.write(f"**Historical Mode:** {'Yes' if run_data.get('use_historical') else 'No'}")
        with col3:
            st.write(f"**Test Inputs:** {run_data.get('test_suite_size', 0)}")
            st.write(f"**Duration:** {run_data.get('duration_seconds', 0):.1f}s")
            cost = run_data.get('cost_estimate', {}).get('total', 0)
            st.write(f"**Estimated Cost:** ${cost:.2f}")

    st.divider()

    # Main scores section
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Script Quality")

        if aggregation and "script_quality" in aggregation:
            sq = aggregation["script_quality"]
            score_card(
                label="Average Score",
                value=sq.get("mean", 0),
                help_text="Average of 5 LLM-judged dimensions",
            )
            st.caption(f"Based on {sq.get('count', 0)} scripts")
        else:
            stats = run_data.get("statistics", {})
            score_card(
                label="Average Score",
                value=stats.get("script_quality_mean", 0),
            )

        st.divider()

        # System metrics
        st.subheader("System Metrics")

        if aggregation and "system_metrics" in aggregation:
            sys_metrics = aggregation["system_metrics"]

            col_t, col_tc = st.columns(2)
            with col_t:
                timing = sys_metrics.get("timing_accuracy", {})
                st.metric("Timing Accuracy", f"{timing.get('mean', 0):.2f} / 5")
            with col_tc:
                template = sys_metrics.get("template_compatibility", {})
                st.metric("Template Compat.", f"{template.get('mean', 0):.2f} / 5")

    with col2:
        st.subheader("Dimension Scores")

        if aggregation and "by_dimension" in aggregation:
            # Radar chart
            fig = radar_chart(aggregation["by_dimension"], title="All 7 Dimensions")
            st.plotly_chart(fig, width="stretch")

    # Script quality statistics (full width for better display)
    if aggregation and "script_quality" in aggregation:
        sq = aggregation["script_quality"]
        st.subheader("Script Quality Statistics")
        stat_row(sq)

    st.divider()

    # Dimension breakdown table
    st.subheader("Score Breakdown by Dimension")

    if aggregation and "by_dimension" in aggregation:
        dim_data = aggregation["by_dimension"]

        # Create DataFrame for display
        import pandas as pd

        rows = []
        for dim_key in SCRIPT_QUALITY_DIMENSIONS + ["timing_accuracy", "template_compatibility"]:
            dim_stats = dim_data.get(dim_key, {})
            rows.append({
                "Dimension": DIMENSION_NAMES.get(dim_key, dim_key),
                "Mean": f"{dim_stats.get('mean', 0):.2f}",
                "Median": f"{dim_stats.get('median', 0):.2f}",
                "Std Dev": f"{dim_stats.get('std', 0):.2f}",
                "Min": dim_stats.get('min', 'N/A'),
                "Max": dim_stats.get('max', 'N/A'),
                "Count": dim_stats.get('count', 0),
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, width="stretch", hide_index=True)

    st.divider()

    # Breakdowns
    st.subheader("Breakdowns")

    if aggregation:
        tab1, tab2, tab3 = st.tabs(["By Video Type", "By Duration", "By Platform"])

        with tab1:
            by_type = aggregation.get("by_video_type", {})
            if by_type:
                fig = breakdown_bar_chart(by_type, title="Script Quality by Video Type")
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("No breakdown by video type available.")

        with tab2:
            by_duration = aggregation.get("by_duration_range", {})
            if by_duration:
                fig = breakdown_bar_chart(by_duration, title="Script Quality by Duration")
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("No breakdown by duration available.")

        with tab3:
            by_platform = aggregation.get("by_platform", {})
            if by_platform:
                fig = breakdown_bar_chart(by_platform, title="Script Quality by Platform")
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("No breakdown by platform available.")

    st.divider()

    # Feedback themes
    st.subheader("Feedback Themes")

    if aggregation and "feedback_themes" in aggregation:
        themes = aggregation["feedback_themes"]
        feedback_themes_table(themes)
    else:
        st.info("No feedback themes available. Run aggregation to generate themes.")

    st.divider()

    # Individual script results
    st.subheader("Individual Script Results")

    results = run_data.get("results", [])

    if results:
        # Add search/filter
        search = st.text_input("Search by subject", "")

        if search:
            results = [r for r in results if search.lower() in r.get("test_input", {}).get("subject", "").lower()]

        st.caption(f"Showing {min(len(results), 20)} of {len(results)} results")

        # Script expanders
        for i, result in enumerate(results[:20]):
            test_input = result.get("test_input", {})
            script_quality = result.get("script_quality_score", 0)

            with st.expander(
                f"**{test_input.get('video_type', 'Unknown')}**: {test_input.get('subject', 'No subject')[:60]}... (Score: {script_quality:.2f})"
            ):
                # Score summary
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Script Quality", f"{script_quality:.2f}")
                with col2:
                    timing_score = result.get("scores", {}).get("timing_accuracy", {}).get("score", "N/A")
                    st.metric("Timing", timing_score)
                with col3:
                    template_score = result.get("scores", {}).get("template_compatibility", {}).get("score", "N/A")
                    st.metric("Template", template_score)

                # Dimension scores
                st.write("**Dimension Scores:**")
                scores = result.get("scores", {})
                dimension_scores_table(scores, show_all=True)

                # Show improvements
                improvements = result.get("all_improvements", [])
                if improvements:
                    st.write("**Improvement Suggestions:**")
                    for imp in improvements[:5]:
                        st.markdown(f"- {imp}")

                # Show generated script
                script_text = result.get("generated_script", "")
                if script_text:
                    st.write("**Generated Script:**")
                    st.text_area("Script", script_text, height=200, disabled=True, label_visibility="collapsed")
    else:
        st.info("No individual results available.")


if __name__ == "__main__":
    main()
