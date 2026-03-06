"""
Comparison Page

Compare two evaluation runs side-by-side.
"""

import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

st.set_page_config(
    page_title="Comparison - Eval-Judge",
    page_icon="⚖️",
    layout="wide",
)

from dashboard.data.loader import list_runs, load_comparison, load_aggregation
from dashboard.components.charts import bar_chart_comparison
from dashboard.components.metrics import classification_badge
from dashboard.components.tables import comparison_table
from dashboard.config import DIMENSION_NAMES, SCRIPT_QUALITY_DIMENSIONS, SYSTEM_METRIC_DIMENSIONS


def main():
    st.title("⚖️ Prompt Comparison")

    # Get available runs
    runs = list_runs()

    if len(runs) < 2:
        st.warning("Need at least 2 evaluation runs to compare.")
        return

    # Run selectors
    col1, col2 = st.columns(2)

    run_options = {
        f"{r['prompt_version']} ({r['run_id'][:20]}...)": r['run_id']
        for r in runs
    }
    run_labels = list(run_options.keys())

    with col1:
        st.subheader("Baseline Run")
        baseline_label = st.selectbox(
            "Select baseline",
            options=run_labels,
            index=0,
            key="baseline",
        )
        baseline_id = run_options[baseline_label]

    with col2:
        st.subheader("Comparison Run")
        # Default to second run if different from baseline
        default_idx = 1 if len(run_labels) > 1 else 0
        comparison_label = st.selectbox(
            "Select comparison",
            options=run_labels,
            index=default_idx,
            key="comparison",
        )
        comparison_id = run_options[comparison_label]

    if baseline_id == comparison_id:
        st.warning("Please select two different runs to compare.")
        return

    st.divider()

    # Load comparison data
    comparison = load_comparison(baseline_id, comparison_id)

    if not comparison:
        st.info("No pre-computed comparison found. Loading aggregations for basic comparison...")

        # Load aggregations for basic comparison
        agg1 = load_aggregation(baseline_id)
        agg2 = load_aggregation(comparison_id)

        if not agg1 or not agg2:
            st.error("Could not load aggregation data for comparison.")
            st.info("Run: `python -m evaluator compare --run1 <baseline> --run2 <comparison>` to generate comparison.")
            return

        # Build basic comparison from aggregations
        comparison = {
            "run1_id": baseline_id,
            "run2_id": comparison_id,
            "run1_prompt": agg1.get("prompt_version", "Run 1"),
            "run2_prompt": agg2.get("prompt_version", "Run 2"),
            "matched_inputs": min(agg1.get("total_evaluated", 0), agg2.get("total_evaluated", 0)),
            "script_quality": {
                "run1_mean": agg1.get("script_quality", {}).get("mean", 0),
                "run2_mean": agg2.get("script_quality", {}).get("mean", 0),
                "delta": agg2.get("script_quality", {}).get("mean", 0) - agg1.get("script_quality", {}).get("mean", 0),
                "classification": "NO_CHANGE",
            },
            "by_dimension": {},
            "system_metrics": {},
        }

        # Build dimension comparisons
        for dim in SCRIPT_QUALITY_DIMENSIONS + SYSTEM_METRIC_DIMENSIONS:
            d1 = agg1.get("by_dimension", {}).get(dim, {})
            d2 = agg2.get("by_dimension", {}).get(dim, {})
            comparison["by_dimension"][dim] = {
                "run1_mean": d1.get("mean", 0),
                "run2_mean": d2.get("mean", 0),
                "delta": d2.get("mean", 0) - d1.get("mean", 0),
                "classification": "NO_CHANGE",
            }

    # Display comparison results
    run1_prompt = comparison.get("run1_prompt", "Baseline")
    run2_prompt = comparison.get("run2_prompt", "Comparison")

    # Overall result
    st.subheader("Overall Result")

    script_quality = comparison.get("script_quality", {})
    classification = script_quality.get("classification", "NO_CHANGE")

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        st.metric(
            label=f"{run1_prompt}",
            value=f"{script_quality.get('run1_mean', 0):.2f}",
        )

    with col2:
        st.metric(
            label=f"{run2_prompt}",
            value=f"{script_quality.get('run2_mean', 0):.2f}",
            delta=f"{script_quality.get('delta', 0):+.2f}",
        )

    with col3:
        st.markdown("**Status:**")
        st.markdown(classification_badge(classification), unsafe_allow_html=True)

        p_value = script_quality.get("p_value")
        if p_value is not None:
            st.caption(f"p-value: {p_value:.4f}")

    st.divider()

    # Dimension comparison chart
    st.subheader("Dimension Comparison")

    by_dim = comparison.get("by_dimension", {})

    # Build score dicts for chart
    run1_scores = {dim: data.get("run1_mean", 0) for dim, data in by_dim.items()}
    run2_scores = {dim: data.get("run2_mean", 0) for dim, data in by_dim.items()}

    fig = bar_chart_comparison(
        run1_scores,
        run2_scores,
        run1_label=run1_prompt,
        run2_label=run2_prompt,
        dimensions=SCRIPT_QUALITY_DIMENSIONS,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Script Quality Dimensions Table
    st.subheader("Script Quality Dimensions")
    comparison_table(comparison, dimensions=SCRIPT_QUALITY_DIMENSIONS)

    st.divider()

    # System Metrics
    st.subheader("System Metrics")

    sys_metrics = comparison.get("system_metrics", {})

    if sys_metrics:
        col1, col2 = st.columns(2)

        with col1:
            timing = sys_metrics.get("timing_accuracy", {})
            if timing and "error" not in timing:
                st.metric(
                    "Timing Accuracy",
                    f"{timing.get('run2_mean', 0):.2f}",
                    delta=f"{timing.get('delta', 0):+.2f}",
                )
            else:
                st.metric("Timing Accuracy", "N/A")

        with col2:
            template = sys_metrics.get("template_compatibility", {})
            if template and "error" not in template:
                st.metric(
                    "Template Compatibility",
                    f"{template.get('run2_mean', 0):.2f}",
                    delta=f"{template.get('delta', 0):+.2f}",
                )
            else:
                st.metric("Template Compatibility", "N/A")
    else:
        # Fall back to by_dimension
        col1, col2 = st.columns(2)
        with col1:
            timing = by_dim.get("timing_accuracy", {})
            st.metric(
                "Timing Accuracy",
                f"{timing.get('run2_mean', 0):.2f}",
                delta=f"{timing.get('delta', 0):+.2f}",
            )
        with col2:
            template = by_dim.get("template_compatibility", {})
            st.metric(
                "Template Compatibility",
                f"{template.get('run2_mean', 0):.2f}",
                delta=f"{template.get('delta', 0):+.2f}",
            )

    st.divider()

    # Feedback theme diff
    st.subheader("Feedback Theme Changes")

    feedback_diff = comparison.get("feedback_theme_diff", {})

    if feedback_diff:
        tab1, tab2, tab3 = st.tabs(["✅ Resolved", "🔄 Persistent", "⚠️ New"])

        with tab1:
            resolved = feedback_diff.get("resolved", [])
            if resolved:
                for theme in resolved:
                    st.markdown(f"- **{theme.get('name', 'Unknown')}** (was {theme.get('count', 0)} occurrences)")
            else:
                st.info("No resolved themes.")

        with tab2:
            persistent = feedback_diff.get("persistent", [])
            if persistent:
                for theme in persistent:
                    delta = theme.get("run2_count", 0) - theme.get("run1_count", 0)
                    delta_str = f"+{delta}" if delta > 0 else str(delta)
                    st.markdown(
                        f"- **{theme.get('name', 'Unknown')}**: {theme.get('run1_count', 0)} → {theme.get('run2_count', 0)} ({delta_str})"
                    )
            else:
                st.info("No persistent themes.")

        with tab3:
            new_themes = feedback_diff.get("new", [])
            if new_themes:
                for theme in new_themes:
                    st.markdown(f"- **{theme.get('name', 'Unknown')}** ({theme.get('count', 0)} occurrences)")
            else:
                st.info("No new themes.")
    else:
        st.info("No feedback theme analysis available.")

    # Summary
    st.divider()
    st.subheader("Summary")

    improvements = comparison.get("improvements", [])
    regressions = comparison.get("regressions", [])

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Improvements:**")
        if improvements:
            for imp in improvements:
                st.markdown(f"- ✅ {imp}")
        else:
            st.caption("No significant improvements")

    with col2:
        st.markdown("**Regressions:**")
        if regressions:
            for reg in regressions:
                st.markdown(f"- ⚠️ {reg}")
        else:
            st.caption("No significant regressions")


if __name__ == "__main__":
    main()
