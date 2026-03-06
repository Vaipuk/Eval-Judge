"""
Hook & Opening Quality Dimension

Evaluates the first 3 lines of the script for engagement and curiosity triggers.
"""

DIMENSION_NAME = "Hook & Opening Quality"

SYSTEM_PROMPT = """You are a video script quality evaluator for Pictory.ai, an AI video creation platform. You evaluate generated scripts on specific quality dimensions using a strict, detailed rubric.

Your evaluation must be:
- Anchored to the rubric criteria — cite specific observable indicators
- Evidence-based — quote or reference specific lines from the script
- Calibrated — 3 means "meets minimum acceptable bar", 5 means "exceptional, no meaningful room for improvement". Use the full 1-5 range.
- Actionable — your improvement suggestions must be specific enough that a prompt engineer could act on them

IMPORTANT: Reason top-down. Start by checking if the script meets score 5 criteria, then 4, then 3, etc. This prevents anchoring bias toward low scores."""

RUBRIC = """## Rubric: Hook & Opening Quality

| Score | Criteria | Observable Indicators |
|-------|----------|----------------------|
| 5 — Exceptional | Immediately compelling; creates curiosity or urgency; clearly establishes the video's value proposition; tailored to the specific topic | Uses a surprising fact, provocative question, or vivid scenario specific to the subject; viewer immediately knows what they'll learn/gain; opening could NOT be swapped to a different topic without rewriting |
| 4 — Strong | Engages the viewer; clear topic introduction; some specificity | References the subject directly; creates mild curiosity; establishes context but hook isn't uniquely compelling |
| 3 — Adequate | States the topic but doesn't create strong engagement | Generic question format ("Have you ever wondered about X?"); topic is named but no unique angle; functional but forgettable |
| 2 — Weak | Generic or overly broad; doesn't hook the viewer | Could apply to almost any topic in the same video type; no curiosity trigger; starts with a definition or dictionary-style opening |
| 1 — Poor | No discernible hook; jumps into content without framing; confusing | No opening frame at all; starts mid-explanation; topic is unclear from the first 3 lines |"""


def build_user_prompt(
    video_type: str,
    subject: str,
    duration_range: str,
    platform: str,
    script_text: str
) -> str:
    """
    Build the user prompt for Hook & Opening Quality evaluation.

    The judge receives only the first 3 lines of the script.
    """
    # Extract first 3 lines
    lines = [line.strip() for line in script_text.strip().split("\n") if line.strip()]
    first_3_lines = "\n".join(lines[:3]) if len(lines) >= 3 else "\n".join(lines)

    return f"""## Task
Evaluate the following video script opening on the dimension: {DIMENSION_NAME}

## Script Metadata
- Video Type: {video_type}
- Subject: {subject}
- Target Duration: {duration_range}
- Platform: {platform}

## Script Opening (First 3 Lines)
{first_3_lines}

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
