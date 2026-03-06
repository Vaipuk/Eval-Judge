"""
Tone & Style Match Dimension

Evaluates alignment of the full script with the expected tone for the video type and platform.
"""

DIMENSION_NAME = "Tone & Style Match"

SYSTEM_PROMPT = """You are a video script quality evaluator for Pictory.ai, an AI video creation platform. You evaluate generated scripts on specific quality dimensions using a strict, detailed rubric.

Your evaluation must be:
- Anchored to the rubric criteria — cite specific observable indicators
- Evidence-based — quote or reference specific lines from the script
- Calibrated — 3 means "meets minimum acceptable bar", 5 means "exceptional, no meaningful room for improvement". Use the full 1-5 range.
- Actionable — your improvement suggestions must be specific enough that a prompt engineer could act on them

IMPORTANT: Reason top-down. Start by checking if the script meets score 5 criteria, then 4, then 3, etc. This prevents anchoring bias toward low scores."""

RUBRIC = """## Rubric: Tone & Style Match

### Tone Expectations by Video Type

| Video Type | Expected Tone | Key Indicators |
|------------|---------------|----------------|
| Explainer | Clear, educational, accessible, balanced pacing | Defines terms when introduced; uses analogies; avoids jargon or explains it; maintains a teacher-like voice |
| Marketing | Persuasive, energetic, benefit-focused, CTA-driven | Emphasizes benefits over features; creates urgency; uses power words; has a clear value proposition; strong CTA |
| Internal Comms | Professional, concise, action-oriented, informative | Business-appropriate language; clear action items; respects reader's time; avoids fluff; states impact |
| Tutorial | Instructional, step-by-step, patient, precise | Uses sequential language (first, next, then); each step is actionable; prerequisites stated; no assumed knowledge |
| Product Intro | Enthusiastic, feature-focused, benefit-driven, demo-friendly | Showcases capabilities; connects features to user problems; builds excitement; includes use cases |

### Platform Modifiers

| Platform | Modifier |
|----------|----------|
| YouTube | Can be longer-form; more detailed; conversational |
| Instagram Reels | Punchy; fast-paced; visual cues; immediate hook |
| TikTok | Ultra-concise; trend-aware; casual tone |
| LinkedIn | Professional; thought-leadership angle; industry terms acceptable |
| General/Other | Default to the video type tone |

### Scoring

| Score | Criteria |
|-------|----------|
| 5 | Tone perfectly matches video type AND platform; consistent throughout; no jarring shifts |
| 4 | Tone appropriate with minor inconsistencies (1-2 lines feel off); platform mostly considered |
| 3 | Tone acceptable but noticeably off in sections; platform influence missing |
| 2 | Tone mismatch is distracting (e.g., casual for Internal Comms, dry for Marketing); multiple sections feel wrong |
| 1 | Tone completely wrong for the video type; feels like wrong video type entirely |"""


def build_user_prompt(
    video_type: str,
    subject: str,
    duration_range: str,
    platform: str,
    script_text: str
) -> str:
    """
    Build the user prompt for Tone & Style Match evaluation.

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
