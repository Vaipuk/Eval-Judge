"""
Completeness & Closure Dimension

Evaluates whether the script has a proper conclusion with summary and CTA.
"""

DIMENSION_NAME = "Completeness & Closure"

SYSTEM_PROMPT = """You are a video script quality evaluator for Pictory.ai, an AI video creation platform. You evaluate generated scripts on specific quality dimensions using a strict, detailed rubric.

Your evaluation must be:
- Anchored to the rubric criteria — cite specific observable indicators
- Evidence-based — quote or reference specific lines from the script
- Calibrated — 3 means "meets minimum acceptable bar", 5 means "exceptional, no meaningful room for improvement". Use the full 1-5 range.
- Actionable — your improvement suggestions must be specific enough that a prompt engineer could act on them

IMPORTANT: Reason top-down. Start by checking if the script meets score 5 criteria, then 4, then 3, etc. This prevents anchoring bias toward low scores."""

RUBRIC = """## Rubric: Completeness & Closure

| Score | Criteria | Observable Indicators |
|-------|----------|----------------------|
| 5 | Natural conclusion; summarizes key points; includes appropriate CTA or closing thought tailored to video type and platform | Summary references specific points from the script; CTA is specific and actionable; feels like a complete piece |
| 4 | Good ending with minor abruptness; CTA present but generic | Summary exists but misses a key point; CTA is present but could be more specific |
| 3 | Ends adequately but feels like it could continue; CTA is vague or missing | Last lines introduce new info instead of wrapping up; generic sign-off; no clear CTA |
| 2 | Abrupt ending; missing summary or CTA; feels unfinished | Script just stops; no wrapping up; last line doesn't feel like a conclusion |
| 1 | Clearly truncated or unfinished; mid-thought ending | Sentence appears cut off; obvious that more content was intended; no conclusion whatsoever |"""


def build_user_prompt(
    video_type: str,
    subject: str,
    duration_range: str,
    platform: str,
    script_text: str
) -> str:
    """
    Build the user prompt for Completeness & Closure evaluation.

    The judge receives the last 5 lines plus script length context.
    """
    # Extract last 5 lines
    lines = [line.strip() for line in script_text.strip().split("\n") if line.strip()]
    total_lines = len(lines)
    last_5_lines = "\n".join(lines[-5:]) if len(lines) >= 5 else "\n".join(lines)

    return f"""## Task
Evaluate the following video script ending on the dimension: {DIMENSION_NAME}

## Script Metadata
- Video Type: {video_type}
- Subject: {subject}
- Target Duration: {duration_range}
- Platform: {platform}
- Total Script Lines: {total_lines}

## Script Ending (Last 5 Lines)
{last_5_lines}

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
