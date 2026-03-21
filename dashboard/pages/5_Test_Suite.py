"""
Test Suite Page

Browse and search test cases.
"""

import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Test Suite - Eval-Judge",
    page_icon="📋",
    layout="wide",
)

from dashboard.data.loader import load_test_suite
from dashboard.config import VIDEO_TYPES, DURATION_RANGES, PLATFORMS


def main():
    st.title("📋 Test Suite Browser")

    # Load test suite
    test_suite = load_test_suite()

    if not test_suite:
        st.error("Failed to load test suite.")
        return

    st.caption(f"Total test cases: {len(test_suite)}")

    # Sidebar filters
    st.sidebar.header("Filters")

    # Search
    search = st.sidebar.text_input("Search subject", "")

    # Video type filter
    all_types = list(set(t.get("video_type", "Unknown") for t in test_suite))
    selected_types = st.sidebar.multiselect(
        "Video Type",
        options=all_types,
        default=all_types,
    )

    # Duration filter
    all_durations = list(set(t.get("duration_range") or "Unknown" for t in test_suite))
    selected_durations = st.sidebar.multiselect(
        "Duration",
        options=all_durations,
        default=all_durations,
    )

    # Platform filter
    all_platforms = list(set(t.get("platform") or "Unknown" for t in test_suite))
    selected_platforms = st.sidebar.multiselect(
        "Platform",
        options=all_platforms,
        default=all_platforms,
    )

    # Filter test cases
    filtered = []
    for t in test_suite:
        video_type = t.get("video_type", "Unknown")
        duration = t.get("duration_range") or "Unknown"
        platform = t.get("platform") or "Unknown"
        subject = t.get("subject", "")

        if video_type not in selected_types:
            continue
        if duration not in selected_durations:
            continue
        if platform not in selected_platforms:
            continue
        if search and search.lower() not in subject.lower():
            continue

        filtered.append(t)

    st.subheader(f"Filtered Results: {len(filtered)} test cases")

    # Pagination
    page_size = 20
    total_pages = max(1, (len(filtered) + page_size - 1) // page_size)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        page = st.number_input(
            "Page",
            min_value=1,
            max_value=total_pages,
            value=1,
            step=1,
        )

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_items = filtered[start_idx:end_idx]

    st.caption(f"Showing {start_idx + 1}-{min(end_idx, len(filtered))} of {len(filtered)}")

    st.divider()

    # Display test cases
    for i, test_case in enumerate(page_items):
        test_id = test_case.get("id", "")[:8]
        video_type = test_case.get("video_type", "Unknown")
        duration = test_case.get("duration_range") or "Unknown"
        platform = test_case.get("platform") or "Unknown"
        subject = test_case.get("subject", "No subject")

        with st.expander(f"**[{test_id}]** {video_type} | {duration} | {platform}"):
            st.markdown("**Subject:**")
            st.text_area(
                "Subject text",
                subject,
                height=150,
                disabled=True,
                label_visibility="collapsed",
                key=f"subject_{i}_{page}",
            )

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.write(f"**ID:** {test_case.get('id', 'N/A')[:20]}...")
            with col2:
                st.write(f"**Video Type:** {video_type}")
            with col3:
                st.write(f"**Duration:** {duration}")
            with col4:
                st.write(f"**Platform:** {platform}")

            # Duration details
            min_sec = test_case.get("duration_min_sec")
            max_sec = test_case.get("duration_max_sec")
            if min_sec or max_sec:
                st.caption(f"Target duration: {min_sec or '?'}s - {max_sec or '?'}s")

    st.divider()

    # Summary statistics
    st.subheader("Test Suite Statistics")

    # Build stats DataFrame
    df = pd.DataFrame(test_suite)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**By Video Type**")
        type_counts = df["video_type"].value_counts()
        st.dataframe(type_counts, width="stretch")

    with col2:
        st.markdown("**By Duration**")
        duration_counts = df["duration_range"].fillna("Unknown").value_counts()
        st.dataframe(duration_counts, width="stretch")

    with col3:
        st.markdown("**By Platform**")
        platform_counts = df["platform"].fillna("Unknown").value_counts()
        st.dataframe(platform_counts, width="stretch")


if __name__ == "__main__":
    main()
