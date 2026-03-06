"""
Timing Accuracy Scorer

Scores scripts based on how well their word count matches the target duration.
Uses 140 WPM as the baseline speaking rate.

Scoring rubric (from spec):
| Score | Criteria |
|-------|----------|
| 5 | Within requested duration range |
| 4 | Within 15 seconds outside range |
| 3 | Within 30 seconds outside range |
| 2 | Within 60 seconds outside range |
| 1 | More than 60 seconds outside range |
"""

from dataclasses import dataclass
from typing import Optional


# Words per minute for video script narration
WPM = 140


@dataclass
class TimingResult:
    """Result from timing accuracy scoring."""
    score: int  # 1-5
    estimated_duration_sec: float
    target_min_sec: Optional[int]
    target_max_sec: Optional[int]
    deviation_sec: float  # How far outside the range (0 if within)
    within_range: bool


def count_words(text: str) -> int:
    """Count words in text."""
    if not text:
        return 0
    return len(text.split())


def estimate_duration_sec(word_count: int) -> float:
    """
    Estimate script duration in seconds based on word count.

    Formula: (word_count / WPM) * 60
    """
    if word_count <= 0:
        return 0.0
    return round((word_count / WPM) * 60, 1)


def calculate_deviation(
    estimated_sec: float,
    min_sec: Optional[int],
    max_sec: Optional[int]
) -> tuple[float, bool]:
    """
    Calculate how far the estimated duration is from the target range.

    Returns:
        (deviation_sec, within_range)
        - deviation_sec: 0 if within range, otherwise distance to nearest bound
        - within_range: True if estimated is between min and max (inclusive)
    """
    # Handle missing duration bounds
    if min_sec is None and max_sec is None:
        # No target specified - can't calculate deviation
        # Treat as "within range" with 0 deviation
        return 0.0, True

    # If only one bound is specified, use it for both
    if min_sec is None:
        min_sec = max_sec
    if max_sec is None:
        max_sec = min_sec

    # Check if within range
    if min_sec <= estimated_sec <= max_sec:
        return 0.0, True

    # Calculate deviation (distance to nearest bound)
    if estimated_sec < min_sec:
        deviation = min_sec - estimated_sec
    else:
        deviation = estimated_sec - max_sec

    return round(deviation, 1), False


def deviation_to_score(deviation_sec: float, within_range: bool) -> int:
    """
    Convert deviation to a 1-5 score.

    | Score | Criteria |
    |-------|----------|
    | 5 | Within requested duration range |
    | 4 | Within 15 seconds outside range |
    | 3 | Within 30 seconds outside range |
    | 2 | Within 60 seconds outside range |
    | 1 | More than 60 seconds outside range |
    """
    if within_range:
        return 5

    if deviation_sec <= 15:
        return 4
    elif deviation_sec <= 30:
        return 3
    elif deviation_sec <= 60:
        return 2
    else:
        return 1


def score_timing(
    script: str,
    duration_min_sec: Optional[int] = None,
    duration_max_sec: Optional[int] = None,
    word_count: Optional[int] = None
) -> TimingResult:
    """
    Score a script's timing accuracy.

    Args:
        script: The generated script text
        duration_min_sec: Minimum target duration in seconds
        duration_max_sec: Maximum target duration in seconds
        word_count: Pre-computed word count (optional, will compute if not provided)

    Returns:
        TimingResult with score and details
    """
    # Get word count
    if word_count is None:
        word_count = count_words(script)

    # Estimate duration
    estimated_sec = estimate_duration_sec(word_count)

    # Calculate deviation
    deviation_sec, within_range = calculate_deviation(
        estimated_sec, duration_min_sec, duration_max_sec
    )

    # Convert to score
    score = deviation_to_score(deviation_sec, within_range)

    return TimingResult(
        score=score,
        estimated_duration_sec=estimated_sec,
        target_min_sec=duration_min_sec,
        target_max_sec=duration_max_sec,
        deviation_sec=deviation_sec,
        within_range=within_range
    )
