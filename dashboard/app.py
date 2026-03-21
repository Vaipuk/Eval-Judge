"""
Eval-Judge Dashboard

Streamlit frontend for viewing evaluation results, comparing prompts,
and running new evaluations.

Run with: streamlit run dashboard/app.py
"""

import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

# Page config must be first Streamlit command
st.set_page_config(
    page_title="Eval-Judge Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

from dashboard.data.loader import list_runs, clear_cache


def main():
    # Sidebar
    with st.sidebar:
        st.title("📊 Eval-Judge")
        st.caption("Script Evaluation Dashboard")

        st.divider()

        # Refresh button
        if st.button("🔄 Refresh Data"):
            clear_cache()
            st.rerun()

        st.divider()

        # Quick stats
        runs = list_runs()
        st.metric("Total Runs", len(runs))

        if runs:
            latest = runs[0]
            st.caption(f"Latest: {latest['prompt_version']}")

    # Main content
    st.title("Welcome to Eval-Judge")

    st.markdown("""
    ### Pictory.ai Script Evaluation System

    Use the sidebar navigation to explore:

    - **📈 Run Report** - View detailed results for a single evaluation run
    - **⚖️ Comparison** - Compare two prompt versions side-by-side
    - **🔍 Filters** - Analyze results by video type, duration, platform
    - **📉 Trends** - Track score trends over time
    - **📋 Test Suite** - Browse test cases and samples
    - **▶️ Run Eval** - Start a new evaluation run
    """)

    st.divider()

    # Show recent runs
    st.subheader("Recent Evaluation Runs")

    runs = list_runs()

    if not runs:
        st.info("No evaluation runs found. Run an evaluation to get started.")
        return

    # Display as cards
    cols = st.columns(3)

    for i, run in enumerate(runs[:6]):
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"**{run['prompt_version']}**")
                st.caption(run['run_id'][:30] + "...")

                col1, col2 = st.columns(2)
                with col1:
                    score = run.get("statistics", {}).get("script_quality_mean", 0)
                    st.metric("Score", f"{score:.2f}" if score else "N/A")
                with col2:
                    st.metric("Inputs", run.get("test_suite_size", 0))

                if run.get("use_historical"):
                    st.caption("📜 Historical mode")
                else:
                    st.caption(f"🤖 {run.get('generation_model', 'unknown')}")


if __name__ == "__main__":
    main()
