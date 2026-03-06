"""
Content Richness & Specificity Dimension

Evaluates the depth, specificity, and informational value of the script content.
"""

DIMENSION_NAME = "Content Richness & Specificity"

SYSTEM_PROMPT = """You are a video script quality evaluator for Pictory.ai, an AI video creation platform. You evaluate generated scripts on specific quality dimensions using a strict, detailed rubric.

Your evaluation must be:
- Anchored to the rubric criteria — cite specific observable indicators
- Evidence-based — quote or reference specific lines from the script
- Calibrated — 3 means "meets minimum acceptable bar", 5 means "exceptional, no meaningful room for improvement". Use the full 1-5 range.
- Actionable — your improvement suggestions must be specific enough that a prompt engineer could act on them

IMPORTANT: Reason top-down. Start by checking if the script meets score 5 criteria, then 4, then 3, etc. This prevents anchoring bias toward low scores.

NOTE: Content richness directly drives Smart Template diversity. Scripts with numbers trigger NUMBER templates, scripts with quotes trigger QUOTE templates, sequential items trigger LIST templates. Consider when generic content limits template variety."""

RUBRIC = """## Rubric: Content Richness & Specificity

| Score | Criteria | Observable Indicators |
|-------|----------|----------------------|
| 5 | Rich with specific details, statistics, examples, and expert references; no filler; content is genuinely informative about the specific subject | Contains 3+ concrete data points or examples; references specific names, tools, or methods; someone could learn something new from this script |
| 4 | Good specificity; mostly concrete with minor generic sections | Contains 1-2 concrete data points; most sentences add new information; minor filler present |
| 3 | Mix of specific and generic content | Some concrete details but padded with general statements; feels surface-level; could go deeper |
| 2 | Mostly generic; lacks concrete details or examples | Relies on vague claims ("many people," "studies show"); no specific names, numbers, or examples; feels like a template |
| 1 | Entirely generic and vague; could apply to any topic | Swap the subject name and the script still works for any other topic; pure filler; no information value |"""


def build_user_prompt(
    video_type: str,
    subject: str,
    duration_range: str,
    platform: str,
    script_text: str
) -> str:
    """
    Build the user prompt for Content Richness & Specificity evaluation.

    The judge receives the full script.
    """
    return f"""## Task
Evaluate the following video script on the dimension: {DIMENSION_NAME}

## Script Metadata
- Video Type: {video_type}
- Subject: {subject}
- Target Duration: {duration_range}
- Platform: {platform}

## Full Script
{script_text}

{RUBRIC}

## Required Output Format (JSON)
Think step by step, then provide your evaluation. Start from score 5 and work down until you find the best match.

{{
  "dimension": "{DIMENSION_NAME}",
  "chain_of_thought": "<your step-by-step reasoning analyzing the script against each rubric level, starting from score 5 and working down until you find the best match>",
  "score": <1-5>,
  "justification": "<2-3 sentence summary of why this score>",
  "evidence": ["<specific line or pattern from script supporting the score>", ...],
  "improvements": ["<specific, actionable suggestion that would raise the score>", ...]
}}"""
