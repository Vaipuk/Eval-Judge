"""
Tests for the timing accuracy scorer.

Tests cover:
- Word counting
- Duration estimation (140 WPM)
- Deviation calculation
- Score assignment based on rubric
"""

from scorers.timing import (
    count_words,
    estimate_duration_sec,
    calculate_deviation,
    deviation_to_score,
    score_timing,
    WPM,
)


class TestCountWords:
    """Tests for word counting."""

    def test_empty_string(self):
        assert count_words("") == 0

    def test_none_like_empty(self):
        assert count_words("") == 0

    def test_single_word(self):
        assert count_words("hello") == 1

    def test_multiple_words(self):
        assert count_words("hello world foo bar") == 4

    def test_with_newlines(self):
        assert count_words("hello\nworld\nfoo") == 3

    def test_with_extra_spaces(self):
        assert count_words("hello   world    foo") == 3

    def test_with_punctuation(self):
        # Punctuation attached to words doesn't split them
        assert count_words("Hello, world! How are you?") == 5


class TestEstimateDurationSec:
    """Tests for duration estimation at 140 WPM."""

    def test_zero_words(self):
        assert estimate_duration_sec(0) == 0.0

    def test_140_words_equals_60_sec(self):
        # 140 words at 140 WPM = 1 minute = 60 seconds
        assert estimate_duration_sec(140) == 60.0

    def test_280_words_equals_120_sec(self):
        # 280 words at 140 WPM = 2 minutes = 120 seconds
        assert estimate_duration_sec(280) == 120.0

    def test_70_words_equals_30_sec(self):
        # 70 words at 140 WPM = 0.5 minutes = 30 seconds
        assert estimate_duration_sec(70) == 30.0

    def test_wpm_constant(self):
        # Verify WPM constant is 140
        assert WPM == 140


class TestCalculateDeviation:
    """Tests for deviation calculation."""

    def test_within_range_exact_min(self):
        deviation, within = calculate_deviation(60, 60, 120)
        assert deviation == 0.0
        assert within is True

    def test_within_range_exact_max(self):
        deviation, within = calculate_deviation(120, 60, 120)
        assert deviation == 0.0
        assert within is True

    def test_within_range_middle(self):
        deviation, within = calculate_deviation(90, 60, 120)
        assert deviation == 0.0
        assert within is True

    def test_below_range(self):
        deviation, within = calculate_deviation(50, 60, 120)
        assert deviation == 10.0
        assert within is False

    def test_above_range(self):
        deviation, within = calculate_deviation(130, 60, 120)
        assert deviation == 10.0
        assert within is False

    def test_no_bounds(self):
        # No target = within range by default
        deviation, within = calculate_deviation(100, None, None)
        assert deviation == 0.0
        assert within is True

    def test_only_min_bound(self):
        deviation, within = calculate_deviation(50, 60, None)
        assert deviation == 10.0
        assert within is False

    def test_only_max_bound(self):
        deviation, within = calculate_deviation(130, None, 120)
        assert deviation == 10.0
        assert within is False

    def test_single_point_range(self):
        # min == max (e.g., "1min" -> 60, 60)
        deviation, within = calculate_deviation(60, 60, 60)
        assert deviation == 0.0
        assert within is True


class TestDeviationToScore:
    """Tests for converting deviation to 1-5 score."""

    def test_within_range_score_5(self):
        assert deviation_to_score(0, within_range=True) == 5

    def test_within_15_sec_score_4(self):
        assert deviation_to_score(10, within_range=False) == 4
        assert deviation_to_score(15, within_range=False) == 4

    def test_within_30_sec_score_3(self):
        assert deviation_to_score(16, within_range=False) == 3
        assert deviation_to_score(30, within_range=False) == 3

    def test_within_60_sec_score_2(self):
        assert deviation_to_score(31, within_range=False) == 2
        assert deviation_to_score(60, within_range=False) == 2

    def test_beyond_60_sec_score_1(self):
        assert deviation_to_score(61, within_range=False) == 1
        assert deviation_to_score(120, within_range=False) == 1


class TestScoreTiming:
    """Integration tests for the full scoring function."""

    def test_perfect_timing_score_5(self):
        # 140 words = 60 seconds, target 60-120 seconds
        script = " ".join(["word"] * 140)
        result = score_timing(script, duration_min_sec=60, duration_max_sec=120)

        assert result.score == 5
        assert result.within_range is True
        assert result.deviation_sec == 0.0
        assert result.estimated_duration_sec == 60.0

    def test_slightly_under_score_4(self):
        # 126 words = 54 seconds, target 60-120 -> 6 sec under
        script = " ".join(["word"] * 126)
        result = score_timing(script, duration_min_sec=60, duration_max_sec=120)

        assert result.score == 4
        assert result.within_range is False
        assert result.deviation_sec == 6.0

    def test_moderately_under_score_3(self):
        # 93 words = 39.9 seconds, target 60-120 -> ~20 sec under (within 30s)
        script = " ".join(["word"] * 93)
        result = score_timing(script, duration_min_sec=60, duration_max_sec=120)

        assert result.score == 3
        assert 15 < result.deviation_sec <= 30

    def test_significantly_under_score_2(self):
        # 58 words = 24.9 seconds, target 60-120 -> ~35 sec under (within 60s)
        script = " ".join(["word"] * 58)
        result = score_timing(script, duration_min_sec=60, duration_max_sec=120)

        assert result.score == 2
        assert 30 < result.deviation_sec <= 60

    def test_way_under_score_1(self):
        # 0 words = 0 seconds, target 120-180 -> 120 sec under (>60s)
        script = ""
        result = score_timing(script, duration_min_sec=120, duration_max_sec=180)

        assert result.score == 1
        assert result.deviation_sec > 60

    def test_over_target_score_4(self):
        # 196 words = 84 seconds, target 60-70 -> 14 sec over
        script = " ".join(["word"] * 196)
        result = score_timing(script, duration_min_sec=60, duration_max_sec=70)

        assert result.score == 4
        assert result.deviation_sec == 14.0

    def test_precomputed_word_count(self):
        # Test passing word_count directly
        result = score_timing("ignored", duration_min_sec=60, duration_max_sec=120, word_count=140)

        assert result.score == 5
        assert result.estimated_duration_sec == 60.0

    def test_no_duration_target(self):
        # No target = automatic score 5
        script = " ".join(["word"] * 100)
        result = score_timing(script, duration_min_sec=None, duration_max_sec=None)

        assert result.score == 5
        assert result.within_range is True

    def test_result_contains_metadata(self):
        script = " ".join(["word"] * 140)
        result = score_timing(script, duration_min_sec=60, duration_max_sec=120)

        assert result.target_min_sec == 60
        assert result.target_max_sec == 120
        assert result.estimated_duration_sec == 60.0


class TestRealWorldScenarios:
    """Tests based on realistic script scenarios."""

    def test_short_tiktok_script(self):
        # TikTok: ~15-30 seconds, so 35-70 words
        # 50 words = 21.4 seconds
        script = " ".join(["word"] * 50)
        result = score_timing(script, duration_min_sec=15, duration_max_sec=30)

        assert result.score == 5  # 21.4s is within 15-30s

    def test_youtube_explainer(self):
        # YouTube explainer: 2-3 minutes, so 280-420 words
        # 350 words = 150 seconds = 2.5 minutes
        script = " ".join(["word"] * 350)
        result = score_timing(script, duration_min_sec=120, duration_max_sec=180)

        assert result.score == 5  # 150s is within 120-180s

    def test_one_minute_target(self):
        # Single target "1min" -> min=60, max=60
        # 140 words = exactly 60 seconds
        script = " ".join(["word"] * 140)
        result = score_timing(script, duration_min_sec=60, duration_max_sec=60)

        assert result.score == 5
        assert result.within_range is True
