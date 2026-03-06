"""
Deterministic scorers for the Pictory Eval Judge.

This package contains scoring functions that don't require LLM calls:
- timing: Scores scripts based on word count vs. target duration
- template_compat: Scores scripts based on Smart Template category distribution
"""

from .timing import score_timing, TimingResult
from .template_compat import score_template_compatibility, TemplateResult

__all__ = [
    "score_timing",
    "TimingResult",
    "score_template_compatibility",
    "TemplateResult",
]
