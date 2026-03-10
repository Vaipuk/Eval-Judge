"""Data loading utilities with Streamlit caching."""

import json
from pathlib import Path
from typing import Optional

import streamlit as st

from dashboard.config import DATA_DIR, RUNS_DIR


@st.cache_data(ttl=30)  # Short TTL - run list changes frequently
def list_runs() -> list[dict]:
    """
    List all completed evaluation runs with metadata.

    Returns list of dicts with: run_id, prompt_version, timestamp, test_suite_size, has_aggregation
    """
    runs = []

    for f in RUNS_DIR.glob("eval-*.json"):
        # Skip aggregation and partial files
        if "_aggregation" in f.name or "_partial" in f.name:
            continue

        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)

            run_id = data.get("run_id", f.stem)
            runs.append({
                "run_id": run_id,
                "prompt_version": data.get("prompt_version", "unknown"),
                "timestamp": data.get("timestamp", ""),
                "test_suite_size": data.get("test_suite_size", 0),
                "duration_seconds": data.get("duration_seconds", 0),
                "generation_model": data.get("generation_model", "unknown"),
                "judge_model": data.get("judge_model", "unknown"),
                "use_historical": data.get("use_historical", False),
                "has_aggregation": (RUNS_DIR / f"{run_id}_aggregation.json").exists(),
                "statistics": data.get("statistics", {}),
            })
        except (json.JSONDecodeError, KeyError) as e:
            st.warning(f"Error loading {f.name}: {e}")
            continue

    # Sort by timestamp descending
    runs.sort(key=lambda x: x["timestamp"], reverse=True)
    return runs


@st.cache_data
def load_run(run_id: str) -> Optional[dict]:
    """Load full run result JSON."""
    path = RUNS_DIR / f"{run_id}.json"

    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(ttl=60)  # Short TTL - aggregations can be generated
def load_aggregation(run_id: str) -> Optional[dict]:
    """Load aggregation for a run if exists."""
    path = RUNS_DIR / f"{run_id}_aggregation.json"

    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(ttl=60)  # Short TTL - comparisons can be generated
def load_comparison(run1_id: str, run2_id: str) -> Optional[dict]:
    """Load existing comparison between two runs."""
    # Try both orderings
    path1 = RUNS_DIR / f"compare_{run1_id}_vs_{run2_id}.json"
    path2 = RUNS_DIR / f"compare_{run2_id}_vs_{run1_id}.json"

    if path1.exists():
        with open(path1, "r", encoding="utf-8") as f:
            return json.load(f)
    elif path2.exists():
        with open(path2, "r", encoding="utf-8") as f:
            return json.load(f)

    return None


@st.cache_data
def load_test_suite() -> list[dict]:
    """Load test suite."""
    path = DATA_DIR / "test_suite.json"

    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_prompt_versions() -> list[dict]:
    """Load prompt registry."""
    path = DATA_DIR / "prompt_versions.json"

    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("prompt_versions", [])


def clear_cache():
    """Clear all cached data."""
    st.cache_data.clear()
