"""
Structural Flow & Coherence Dimension

Evaluates narrative arc, transitions, and logical progression of the full script.
"""

DIMENSION_NAME = "Structural Flow & Coherence"

SYSTEM_PROMPT = """You are a video script quality evaluator for Pictory.ai, an AI video creation platform. You evaluate generated scripts on specific quality dimensions using a strict, detailed rubric.

Your evaluation must be:
- Anchored to the rubric criteria — cite specific observable indicators
- Evidence-based — quote or reference specific lines from the script
- Calibrated — 3 means "meets minimum acceptable bar", 5 means "exceptional, no meaningful room for improvement". Use the full 1-5 range.
- Actionable — your improvement suggestions must be specific enough that a prompt engineer could act on them

IMPORTANT: Reason top-down. Start by checking if the script meets score 5 criteria, then 4, then 3, etc. This prevents anchoring bias toward low scores."""

RUBRIC = """## Rubric: Structural Flow & Coherence

### Expected Structures by Video Type

| Video Type | Expected Arc |
|------------|-------------|
| Explainer | Hook → Problem/Context → Explanation → Examples → Summary → CTA |
| Marketing | Hook → Pain Point → Solution → Benefits → Social Proof → CTA |
| Internal Comms | Context → Key Message → Details → Action Items → Next Steps |
| Tutorial | Overview → Prerequisites → Step-by-Step → Tips → Recap |
| Product Intro | Hook → Problem → Product Overview → Features → Demo Points → CTA |

### Scoring

| Score | Criteria | Observable Indicators |
|-------|----------|----------------------|
| 5 | Clear narrative arc matching the video type; smooth transitions; logical progression; strong conclusion | Each section flows naturally to the next; transitional phrases present; no content feels out of place; structure matches expected arc |
| 4 | Good flow with minor awkward transitions; structure mostly matches expected arc | 1-2 transitions feel abrupt; overall arc is correct; minor reordering would improve flow |
| 3 | Acceptable structure but feels choppy or missing clear transitions | Sections exist but transitions are just topic jumps; reader can follow but has to work at it; missing 1 expected section |
| 2 | Disjointed; topics jump without connection; weak conclusion | No transitional language; content blocks feel randomly ordered; missing 2+ expected sections; ending is abrupt |
| 1 | No discernible structure; incoherent flow | Cannot identify an arc; content contradicts itself or repeats; feels like disconnected bullet points |"""


def build_user_prompt(
    video_type: str,
    subject: str,
    duration_range: str,
    platform: str,
    script_text: str
) -> str:
    """
    Build the user prompt for Structural Flow & Coherence evaluation.

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
