"""Prompt builders for each LLM-judged dimension."""

from .hook_quality import SYSTEM_PROMPT as HOOK_SYSTEM, build_user_prompt as build_hook_prompt
from .tone_match import SYSTEM_PROMPT as TONE_SYSTEM, build_user_prompt as build_tone_prompt
from .structural_flow import SYSTEM_PROMPT as FLOW_SYSTEM, build_user_prompt as build_flow_prompt
from .content_richness import SYSTEM_PROMPT as RICHNESS_SYSTEM, build_user_prompt as build_richness_prompt
from .completeness import SYSTEM_PROMPT as COMPLETENESS_SYSTEM, build_user_prompt as build_completeness_prompt

__all__ = [
    "HOOK_SYSTEM", "build_hook_prompt",
    "TONE_SYSTEM", "build_tone_prompt",
    "FLOW_SYSTEM", "build_flow_prompt",
    "RICHNESS_SYSTEM", "build_richness_prompt",
    "COMPLETENESS_SYSTEM", "build_completeness_prompt",
]
