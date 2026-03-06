"""
Run Evaluation Page

Trigger new evaluation runs via CLI.
"""

import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import subprocess

st.set_page_config(
    page_title="Run Evaluation - Eval-Judge",
    page_icon="▶️",
    layout="wide",
)

from dashboard.data.loader import list_runs, load_prompt_versions, clear_cache


def run_evaluation_command(prompt_version: str, max_inputs: int) -> tuple[int, str]:
    """
    Run evaluation via CLI.

    Returns:
        (return_code, output)
    """
    cmd = [
        sys.executable, "-m", "evaluator", "run",
        "--prompt", prompt_version,
        "--max-inputs", str(max_inputs),
        "-a",  # Auto-approve (skip confirmation)
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout
        )
        output = result.stdout + result.stderr
        return result.returncode, output
    except subprocess.TimeoutExpired:
        return -1, "Evaluation timed out after 1 hour."
    except Exception as e:
        return -1, f"Error: {str(e)}"


def main():
    st.title("▶️ Run Evaluation")

    # Load prompt versions
    prompts = load_prompt_versions()

    if not prompts:
        st.error("No prompt versions found in registry.")
        return

    # Configuration
    st.subheader("Configuration")

    col1, col2 = st.columns(2)

    with col1:
        prompt_options = {p["id"]: p for p in prompts}
        selected_prompt = st.selectbox(
            "Prompt Version",
            options=list(prompt_options.keys()),
        )

        if selected_prompt:
            prompt_info = prompt_options[selected_prompt]
            st.caption(f"Type: {prompt_info.get('type', 'unknown')}")
            st.caption(f"Model: {prompt_info.get('model', 'unknown')}")
            st.caption(f"Status: {prompt_info.get('status', 'unknown')}")
            if prompt_info.get("use_historical"):
                st.info("📜 Historical mode: uses pre-generated scripts")

    with col2:
        max_inputs = st.number_input(
            "Max Inputs",
            min_value=1,
            max_value=500,
            value=50,
            step=10,
            help="Number of test cases to evaluate",
        )

        st.caption(f"Estimated time: ~{max_inputs * 2} minutes")

    st.divider()

    # Run button
    if "eval_running" not in st.session_state:
        st.session_state.eval_running = False
    if "eval_output" not in st.session_state:
        st.session_state.eval_output = None

    col1, col2 = st.columns([1, 3])

    with col1:
        if st.button(
            "🚀 Start Evaluation",
            width="stretch",
            disabled=st.session_state.eval_running,
            type="primary",
        ):
            st.session_state.eval_running = True
            st.session_state.eval_output = None
            st.rerun()

    if st.session_state.eval_running:
        with st.spinner(f"Running evaluation for {selected_prompt}..."):
            return_code, output = run_evaluation_command(selected_prompt, max_inputs)

            st.session_state.eval_running = False
            st.session_state.eval_output = {
                "return_code": return_code,
                "output": output,
            }

            # Clear cache to show new run
            clear_cache()
            st.rerun()

    # Show output
    if st.session_state.eval_output:
        result = st.session_state.eval_output

        if result["return_code"] == 0:
            st.success("✅ Evaluation completed successfully!")
        else:
            st.error(f"❌ Evaluation failed with code {result['return_code']}")

        with st.expander("Show output", expanded=result["return_code"] != 0):
            st.code(result["output"], language="text")

        if st.button("Clear output"):
            st.session_state.eval_output = None
            st.rerun()

    st.divider()

    # Recent runs
    st.subheader("Recent Runs")

    runs = list_runs()

    if runs:
        for run in runs[:5]:
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

                with col1:
                    st.markdown(f"**{run['prompt_version']}**")
                    st.caption(run["run_id"][:40] + "...")

                with col2:
                    st.metric("Inputs", run.get("test_suite_size", 0))

                with col3:
                    score = run.get("statistics", {}).get("script_quality_mean", 0)
                    st.metric("Score", f"{score:.2f}" if score else "N/A")

                with col4:
                    duration = run.get("duration_seconds", 0)
                    st.metric("Duration", f"{duration:.0f}s")
    else:
        st.info("No runs yet. Start an evaluation above.")

    st.divider()

    # CLI reference
    with st.expander("CLI Reference"):
        st.markdown("""
        **Run evaluation:**
        ```bash
        python -m evaluator run --prompt <version> --max-inputs <n>
        ```

        **Compare runs:**
        ```bash
        python -m evaluator compare --run1 <run_id> --run2 <run_id>
        ```

        **Generate report:**
        ```bash
        python -m evaluator report --run <run_id>
        ```

        **List prompts:**
        ```bash
        python -m evaluator prompts list
        ```
        """)


if __name__ == "__main__":
    main()
