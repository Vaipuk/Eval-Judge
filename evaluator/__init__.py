"""
Evaluation Pipeline Package

Orchestrates script generation, judging, aggregation, and comparison.
"""

from .prompt_registry import (
    get_prompt,
    get_prompt_entry,
    list_prompts,
    register_prompt,
    set_status,
)
from .run import run_evaluation
from .aggregate import aggregate_run
from .compare import compare_runs
from .report import generate_report, generate_comparison_report
