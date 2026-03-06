"""
Main Evaluation Entry Point

Takes a script record and runs all 7 scorers (2 deterministic + 5 LLM).
Returns the full judge output schema from Section 4.6 of the spec.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

from .config import get_judge_client, WEIGHTS, SCRIPT_QUALITY_DIMENSIONS, BaseJudge
from .prompts import (
    HOOK_SYSTEM, build_hook_prompt,
    TONE_SYSTEM, build_tone_prompt,
    FLOW_SYSTEM, build_flow_prompt,
    RICHNESS_SYSTEM, build_richness_prompt,
    COMPLETENESS_SYSTEM, build_completeness_prompt,
)

# Import scorers from Step 1
from scorers.timing import score_timing, TimingResult
from scorers.template_compat import score_template_compatibility, TemplateResult


@dataclass
class DimensionResult:
    """Result from a single LLM-judged dimension."""
    score: Optional[int] = None
    chain_of_thought: Optional[str] = None
    justification: Optional[str] = None
    evidence: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class JudgeResult:
    """Complete judge output for a single script."""
    script_id: str
    prompt_version: str
    timestamp: str
    metadata: dict
    scores: dict
    composite_score: float  # Legacy weighted composite (all 7 dimensions)
    script_quality_score: float  # New: average of 5 LLM-judged dimensions
    all_improvements: list[str]


def _call_dimension_with_retry(
    judge: BaseJudge,
    system_prompt: str,
    user_prompt: str,
    dimension_name: str,
    max_retries: int = 2
) -> DimensionResult:
    """
    Call the judge for a dimension with retry on failure.

    Args:
        judge: The judge client
        system_prompt: System prompt for this dimension
        user_prompt: User prompt with script and rubric
        dimension_name: Name of the dimension (for error messages)
        max_retries: Number of attempts before giving up

    Returns:
        DimensionResult with score and details, or error message
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            response = judge.evaluate(system_prompt, user_prompt)

            # Validate required fields
            score = response.get("score")
            if score is None or not isinstance(score, int) or score < 1 or score > 5:
                raise ValueError(f"Invalid score: {score}")

            return DimensionResult(
                score=score,
                chain_of_thought=response.get("chain_of_thought", ""),
                justification=response.get("justification", ""),
                evidence=response.get("evidence", []),
                improvements=response.get("improvements", []),
            )

        except Exception as e:
            last_error = str(e)
            if attempt < max_retries - 1:
                continue  # Retry
            break

    # All retries failed
    return DimensionResult(
        error=f"Failed to evaluate {dimension_name} after {max_retries} attempts: {last_error}"
    )


def _timing_result_to_dict(result: TimingResult) -> dict:
    """Convert TimingResult to dict for JSON serialization."""
    return {
        "score": result.score,
        "estimated_duration_sec": result.estimated_duration_sec,
        "target_min_sec": result.target_min_sec,
        "target_max_sec": result.target_max_sec,
        "deviation_sec": result.deviation_sec,
        "within_range": result.within_range,
    }


def _template_result_to_dict(result: TemplateResult) -> dict:
    """Convert TemplateResult to dict for JSON serialization."""
    return {
        "score": result.score,
        "categories_triggered": result.categories_triggered,
        "category_count": result.category_count,
        "distribution": result.distribution,
        "issues": result.issues,
        "title_at_start": result.title_at_start,
        "section_spacing_ok": result.section_spacing_ok,
    }


def _dimension_result_to_dict(result: DimensionResult) -> dict:
    """Convert DimensionResult to dict for JSON serialization."""
    if result.error:
        return {"error": result.error}

    return {
        "score": result.score,
        "chain_of_thought": result.chain_of_thought,
        "justification": result.justification,
        "evidence": result.evidence,
        "improvements": result.improvements,
    }


def compute_composite_score(scores: dict) -> float:
    """
    Compute weighted composite score (legacy, includes all 7 dimensions).

    Uses weights from spec Section 4.1:
    - timing_accuracy: 20%
    - template_compatibility: 20%
    - hook_quality: 10%
    - tone_match: 15%
    - structural_flow: 15%
    - content_richness: 10%
    - completeness: 10%
    """
    total_weight = 0.0
    weighted_sum = 0.0

    for dimension, weight in WEIGHTS.items():
        dim_data = scores.get(dimension, {})
        score = dim_data.get("score")

        if score is not None and isinstance(score, (int, float)):
            weighted_sum += score * weight
            total_weight += weight

    if total_weight == 0:
        return 0.0

    # Normalize in case some dimensions failed
    return round(weighted_sum / total_weight * (1.0 / max(total_weight, 1.0)) * total_weight, 2)


def compute_script_quality_score(scores: dict) -> float:
    """
    Compute Script Quality score as simple average of 5 LLM-judged dimensions.

    Dimensions (equal weight):
    - hook_quality
    - tone_match
    - structural_flow
    - content_richness
    - completeness

    System metrics (timing_accuracy, template_compatibility) are NOT included.
    """
    valid_scores = []

    for dimension in SCRIPT_QUALITY_DIMENSIONS:
        dim_data = scores.get(dimension, {})
        score = dim_data.get("score")

        if score is not None and isinstance(score, (int, float)):
            valid_scores.append(score)

    if not valid_scores:
        return 0.0

    return round(sum(valid_scores) / len(valid_scores), 2)


def collect_all_improvements(scores: dict) -> list[str]:
    """
    Collect all improvements from LLM dimensions and issues from deterministic scorers.
    """
    all_improvements = []

    # Deterministic scorer issues
    timing = scores.get("timing_accuracy", {})
    if not timing.get("within_range", True):
        deviation = timing.get("deviation_sec", 0)
        if deviation > 0:
            all_improvements.append(
                f"Timing: Script is {deviation:.1f} seconds outside target duration range"
            )

    template = scores.get("template_compatibility", {})
    for issue in template.get("issues", []):
        all_improvements.append(f"Template: {issue}")

    # LLM dimension improvements
    llm_dimensions = ["hook_quality", "tone_match", "structural_flow", "content_richness", "completeness"]
    for dim in llm_dimensions:
        dim_data = scores.get(dim, {})
        for improvement in dim_data.get("improvements", []):
            all_improvements.append(improvement)

    return all_improvements


def evaluate_script(
    record: dict,
    prompt_version: str = "unknown",
    judge: Optional[BaseJudge] = None,
    openai_client=None,
) -> JudgeResult:
    """
    Evaluate a single script record using all 7 scorers.

    Args:
        record: Cleaned script record with fields:
            - id: Script ID
            - video_type: Type of video (Explainer, Marketing, etc.)
            - subject: Topic of the script
            - duration_range: Target duration string (e.g., "1min", "1-2min")
            - duration_min_sec: Minimum target duration in seconds
            - duration_max_sec: Maximum target duration in seconds
            - platform: Target platform (YouTube, TikTok, etc.)
            - script: The generated script text
            - word_count: Number of words in script
            - estimated_time_sec: Estimated duration at 140 WPM

        prompt_version: Version identifier for the prompt being tested
        judge: Optional pre-configured judge client
        openai_client: Optional OpenAI client for template compatibility scorer

    Returns:
        JudgeResult with all scores, composite, and improvements
    """
    # Extract record fields
    script_id = record.get("id", "unknown")
    video_type = record.get("video_type", "Explainer")
    subject = record.get("subject", "Unknown")
    duration_range = record.get("duration_range", "")
    duration_min_sec = record.get("duration_min_sec")
    duration_max_sec = record.get("duration_max_sec")
    platform = record.get("platform", "General")
    script = record.get("script", "")
    word_count = record.get("word_count")

    # Initialize judge if not provided
    if judge is None:
        judge = get_judge_client()

    scores = {}

    # === Deterministic Scorers ===

    # 1. Timing Accuracy
    timing_result = score_timing(
        script=script,
        duration_min_sec=duration_min_sec,
        duration_max_sec=duration_max_sec,
        word_count=word_count
    )
    scores["timing_accuracy"] = _timing_result_to_dict(timing_result)

    # 2. Template Compatibility
    try:
        template_result = score_template_compatibility(script, client=openai_client)
        scores["template_compatibility"] = _template_result_to_dict(template_result)
    except Exception as e:
        scores["template_compatibility"] = {
            "score": None,
            "error": f"Template scoring failed: {str(e)}"
        }

    # === LLM CoT Judge Dimensions ===

    # Build common metadata
    metadata = {
        "video_type": video_type,
        "subject": subject,
        "duration_range": duration_range,
        "platform": platform,
    }

    # 3. Hook & Opening Quality
    hook_prompt = build_hook_prompt(video_type, subject, duration_range, platform, script)
    hook_result = _call_dimension_with_retry(judge, HOOK_SYSTEM, hook_prompt, "Hook Quality")
    scores["hook_quality"] = _dimension_result_to_dict(hook_result)

    # 4. Tone & Style Match
    tone_prompt = build_tone_prompt(video_type, subject, duration_range, platform, script)
    tone_result = _call_dimension_with_retry(judge, TONE_SYSTEM, tone_prompt, "Tone Match")
    scores["tone_match"] = _dimension_result_to_dict(tone_result)

    # 5. Structural Flow & Coherence
    flow_prompt = build_flow_prompt(video_type, subject, duration_range, platform, script)
    flow_result = _call_dimension_with_retry(judge, FLOW_SYSTEM, flow_prompt, "Structural Flow")
    scores["structural_flow"] = _dimension_result_to_dict(flow_result)

    # 6. Content Richness & Specificity
    richness_prompt = build_richness_prompt(video_type, subject, duration_range, platform, script)
    richness_result = _call_dimension_with_retry(judge, RICHNESS_SYSTEM, richness_prompt, "Content Richness")
    scores["content_richness"] = _dimension_result_to_dict(richness_result)

    # 7. Completeness & Closure
    completeness_prompt = build_completeness_prompt(video_type, subject, duration_range, platform, script)
    completeness_result = _call_dimension_with_retry(judge, COMPLETENESS_SYSTEM, completeness_prompt, "Completeness")
    scores["completeness"] = _dimension_result_to_dict(completeness_result)

    # === Compute Scores and Collect Improvements ===

    composite = compute_composite_score(scores)
    script_quality = compute_script_quality_score(scores)
    all_improvements = collect_all_improvements(scores)

    return JudgeResult(
        script_id=script_id,
        prompt_version=prompt_version,
        timestamp=datetime.now(timezone.utc).isoformat(),
        metadata=metadata,
        scores=scores,
        composite_score=composite,
        script_quality_score=script_quality,
        all_improvements=all_improvements,
    )


def judge_result_to_dict(result: JudgeResult) -> dict:
    """Convert JudgeResult to a JSON-serializable dict."""
    return {
        "script_id": result.script_id,
        "prompt_version": result.prompt_version,
        "timestamp": result.timestamp,
        "metadata": result.metadata,
        "scores": result.scores,
        "composite_score": result.composite_score,
        "script_quality_score": result.script_quality_score,
        "all_improvements": result.all_improvements,
    }


def judge_result_to_json(result: JudgeResult, indent: int = 2) -> str:
    """Convert JudgeResult to formatted JSON string."""
    return json.dumps(judge_result_to_dict(result), indent=indent)
