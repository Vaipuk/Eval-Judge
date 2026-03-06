"""
Smart Template Compatibility Scorer

Scores scripts based on how well they work with the Smart Template classifier.
Runs the script through the Video Script Analyzer prompt and evaluates:
- Category coverage (all 7 types triggered)
- TITLE placement (first scene)
- SECTION spacing (every 8-12 scenes)
- Distribution alignment (per target percentages)

Scoring rubric (from spec):
| Score | Criteria |
|-------|----------|
| 5 | 6-7 categories triggered; TITLE at start; SECTIONs well-spaced; distribution within target ranges |
| 4 | 5-6 categories; minor distribution skew; TITLE correct |
| 3 | 4-5 categories; noticeable distribution issues OR TITLE misplaced |
| 2 | 3-4 categories; heavy DEFAULT skew (>60%) |
| 1 | Fewer than 3 categories; almost entirely DEFAULT; structural issues |
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# All valid categories
CATEGORIES = ["TITLE", "SECTION", "LIST", "NUMBER", "QUOTE", "EMPHASIS", "DEFAULT"]

# Target distribution ranges (from spec)
TARGET_DISTRIBUTION = {
    "TITLE": (0.05, 0.10),      # 5-10%
    "SECTION": (0.10, 0.15),    # 10-15%
    "LIST": (0.15, 0.20),       # 15-20%
    "NUMBER": (0.10, 0.15),     # 10-15%
    "QUOTE": (0.10, 0.15),      # 10-15%
    "EMPHASIS": (0.05, 0.10),   # 5-10%
    "DEFAULT": (0.35, 0.45),    # 35-45%
}

# Load the Video Script Analyzer prompt
PROMPT_PATH = Path(__file__).parent / "prompts" / "video_script_analyzer.txt"


def load_analyzer_prompt() -> str:
    """Load the Video Script Analyzer system prompt."""
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


@dataclass
class TemplateResult:
    """Result from template compatibility scoring."""
    score: int  # 1-5
    categories_triggered: list[str]
    category_count: int
    distribution: dict[str, float]
    issues: list[str]
    title_at_start: bool
    section_spacing_ok: bool
    raw_response: Optional[dict] = None


@dataclass
class AnalysisMetrics:
    """Intermediate metrics from analyzing classifier output."""
    categories_triggered: set[str] = field(default_factory=set)
    distribution: dict[str, float] = field(default_factory=dict)
    title_at_start: bool = False
    section_positions: list[int] = field(default_factory=list)
    total_scenes: int = 0
    issues: list[str] = field(default_factory=list)


def get_openai_client() -> OpenAI:
    """Create OpenAI client using API key from environment."""
    api_key = os.getenv("OPEN_API")
    if not api_key:
        raise ValueError("OPEN_API environment variable not set")
    return OpenAI(api_key=api_key)


def prepare_script_for_analysis(script: str) -> str:
    """
    Prepare script for the Video Script Analyzer.

    The analyzer expects numbered lines like:
    1|First line of script
    2|Second line of script
    """
    lines = [line.strip() for line in script.strip().split("\n") if line.strip()]
    numbered_lines = [f"{i+1}|{line}" for i, line in enumerate(lines)]
    return "\n".join(numbered_lines)


def call_template_classifier(client: OpenAI, script: str) -> dict:
    """
    Call the Video Script Analyzer to classify the script.

    Returns the parsed JSON response.
    """
    system_prompt = load_analyzer_prompt()
    prepared_script = prepare_script_for_analysis(script)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prepared_script}
        ],
        response_format={"type": "json_object"},
        temperature=0.1  # Low temperature for consistency
    )

    content = response.choices[0].message.content
    return json.loads(content)


def analyze_classifier_output(output: dict) -> AnalysisMetrics:
    """
    Analyze the classifier output to extract metrics.

    Checks:
    - Which categories were triggered
    - Distribution of categories
    - Whether TITLE is at the start
    - SECTION spacing
    """
    metrics = AnalysisMetrics()

    scenes = output.get("scenes", [])
    if not scenes:
        metrics.issues.append("No scenes in classifier output")
        return metrics

    metrics.total_scenes = len(scenes)

    # Count categories
    category_counts: dict[str, int] = {cat: 0 for cat in CATEGORIES}

    for i, scene in enumerate(scenes):
        category = scene.get("category", "DEFAULT")
        if category not in CATEGORIES:
            category = "DEFAULT"
            metrics.issues.append(f"Unknown category at scene {i+1}: {scene.get('category')}")

        category_counts[category] += 1
        metrics.categories_triggered.add(category)

        # Track SECTION positions for spacing check
        if category == "SECTION":
            metrics.section_positions.append(i + 1)  # 1-indexed

    # Check TITLE at start
    if scenes[0].get("category") == "TITLE":
        metrics.title_at_start = True
    else:
        metrics.issues.append("TITLE not at first scene")

    # Calculate distribution
    for cat, count in category_counts.items():
        metrics.distribution[cat] = round(count / metrics.total_scenes, 3) if metrics.total_scenes > 0 else 0.0

    return metrics


def check_section_spacing(section_positions: list[int], total_scenes: int) -> tuple[bool, list[str]]:
    """
    Check if SECTION scenes are well-spaced (every 8-12 scenes).

    Returns (is_ok, issues)
    """
    issues = []

    if not section_positions:
        if total_scenes > 12:
            issues.append("No SECTION scenes despite script length > 12 scenes")
            return False, issues
        return True, issues  # Short scripts may not need sections

    # Check gaps between sections (and from start to first section)
    positions = [0] + section_positions + [total_scenes + 1]

    gaps = []
    for i in range(len(positions) - 1):
        gap = positions[i + 1] - positions[i]
        gaps.append(gap)

    # Check if gaps are reasonable (allow some flexibility: 6-15 scenes)
    bad_gaps = [g for g in gaps if g > 15]
    if bad_gaps:
        issues.append(f"Large gaps between SECTIONs: {bad_gaps} scenes")
        return False, issues

    return True, issues


def check_distribution_alignment(distribution: dict[str, float]) -> tuple[bool, list[str]]:
    """
    Check if distribution aligns with target ranges.

    Returns (is_ok, issues)
    """
    issues = []
    out_of_range = 0

    for cat, (min_pct, max_pct) in TARGET_DISTRIBUTION.items():
        actual = distribution.get(cat, 0.0)
        if actual < min_pct:
            issues.append(f"{cat} underrepresented: {actual:.1%} (target: {min_pct:.0%}-{max_pct:.0%})")
            out_of_range += 1
        elif actual > max_pct:
            issues.append(f"{cat} overrepresented: {actual:.1%} (target: {min_pct:.0%}-{max_pct:.0%})")
            out_of_range += 1

    # Consider "ok" if at most 2 categories are out of range
    return out_of_range <= 2, issues


def compute_score(metrics: AnalysisMetrics) -> int:
    """
    Compute the template compatibility score (1-5).

    | Score | Criteria |
    |-------|----------|
    | 5 | 6-7 categories triggered; TITLE at start; SECTIONs well-spaced; distribution within target ranges |
    | 4 | 5-6 categories; minor distribution skew; TITLE correct |
    | 3 | 4-5 categories; noticeable distribution issues OR TITLE misplaced |
    | 2 | 3-4 categories; heavy DEFAULT skew (>60%) |
    | 1 | Fewer than 3 categories; almost entirely DEFAULT; structural issues |
    """
    cat_count = len(metrics.categories_triggered)
    default_pct = metrics.distribution.get("DEFAULT", 0.0)

    section_ok, section_issues = check_section_spacing(
        metrics.section_positions, metrics.total_scenes
    )
    metrics.issues.extend(section_issues)

    dist_ok, dist_issues = check_distribution_alignment(metrics.distribution)
    metrics.issues.extend(dist_issues)

    # Check for heavy DEFAULT skew (used in scoring)
    if default_pct > 0.60:
        metrics.issues.append(f"Heavy DEFAULT skew: {default_pct:.1%}")

    # Score 1: Fewer than 3 categories (check first!)
    if cat_count < 3:
        metrics.issues.append(f"Only {cat_count} categories triggered")
        return 1

    # Score 5: 6-7 categories, TITLE at start, good spacing, good distribution
    if cat_count >= 6 and metrics.title_at_start and section_ok and dist_ok:
        return 5

    # Score 4: 5-6 categories, minor distribution skew, TITLE correct
    if cat_count >= 5 and metrics.title_at_start:
        return 4

    # Score 3: 4-5 categories, noticeable issues OR TITLE misplaced
    if cat_count >= 4:
        return 3

    # Score 2: 3-4 categories
    return 2


def score_template_compatibility(
    script: str,
    client: Optional[OpenAI] = None
) -> TemplateResult:
    """
    Score a script's Smart Template compatibility.

    Args:
        script: The generated script text
        client: OpenAI client (optional, will create if not provided)

    Returns:
        TemplateResult with score and details
    """
    if client is None:
        client = get_openai_client()

    # Call the classifier
    try:
        raw_response = call_template_classifier(client, script)
    except Exception as e:
        return TemplateResult(
            score=1,
            categories_triggered=[],
            category_count=0,
            distribution={},
            issues=[f"Classifier API error: {str(e)}"],
            title_at_start=False,
            section_spacing_ok=False,
            raw_response=None
        )

    # Analyze the output
    metrics = analyze_classifier_output(raw_response)

    # Check section spacing
    section_ok, _ = check_section_spacing(
        metrics.section_positions, metrics.total_scenes
    )

    # Compute score
    score = compute_score(metrics)

    return TemplateResult(
        score=score,
        categories_triggered=sorted(list(metrics.categories_triggered)),
        category_count=len(metrics.categories_triggered),
        distribution=metrics.distribution,
        issues=metrics.issues,
        title_at_start=metrics.title_at_start,
        section_spacing_ok=section_ok,
        raw_response=raw_response
    )


def score_template_compatibility_from_analysis(
    classifier_output: dict
) -> TemplateResult:
    """
    Score template compatibility from pre-computed classifier output.

    Use this when you've already called the classifier and want to
    avoid an extra API call.

    Args:
        classifier_output: The raw JSON output from the Video Script Analyzer

    Returns:
        TemplateResult with score and details
    """
    metrics = analyze_classifier_output(classifier_output)

    section_ok, _ = check_section_spacing(
        metrics.section_positions, metrics.total_scenes
    )

    score = compute_score(metrics)

    return TemplateResult(
        score=score,
        categories_triggered=sorted(list(metrics.categories_triggered)),
        category_count=len(metrics.categories_triggered),
        distribution=metrics.distribution,
        issues=metrics.issues,
        title_at_start=metrics.title_at_start,
        section_spacing_ok=section_ok,
        raw_response=classifier_output
    )
