"""
Tests for the Smart Template compatibility scorer.

Tests cover:
- Script preparation for analyzer
- Classifier output analysis
- Section spacing checks
- Distribution alignment checks
- Score computation
- Full scoring (with mocked API)
"""

import pytest
from unittest.mock import Mock, patch

from scorers.template_compat import (
    CATEGORIES,
    TARGET_DISTRIBUTION,
    prepare_script_for_analysis,
    analyze_classifier_output,
    check_section_spacing,
    check_distribution_alignment,
    compute_score,
    score_template_compatibility_from_analysis,
    AnalysisMetrics,
)


class TestPrepareScriptForAnalysis:
    """Tests for script preparation."""

    def test_single_line(self):
        script = "Hello world"
        result = prepare_script_for_analysis(script)
        assert result == "1|Hello world"

    def test_multiple_lines(self):
        script = "Line one\nLine two\nLine three"
        result = prepare_script_for_analysis(script)
        assert result == "1|Line one\n2|Line two\n3|Line three"

    def test_strips_whitespace(self):
        script = "  Line one  \n  Line two  "
        result = prepare_script_for_analysis(script)
        assert result == "1|Line one\n2|Line two"

    def test_skips_empty_lines(self):
        script = "Line one\n\nLine two\n\n\nLine three"
        result = prepare_script_for_analysis(script)
        assert result == "1|Line one\n2|Line two\n3|Line three"


class TestAnalyzeClassifierOutput:
    """Tests for analyzing classifier JSON output."""

    def test_empty_scenes(self):
        output = {"scenes": []}
        metrics = analyze_classifier_output(output)
        assert len(metrics.categories_triggered) == 0
        assert "No scenes in classifier output" in metrics.issues

    def test_single_title_scene(self):
        output = {
            "scenes": [
                {"scene_number": 1, "category": "TITLE"}
            ]
        }
        metrics = analyze_classifier_output(output)
        assert "TITLE" in metrics.categories_triggered
        assert metrics.title_at_start is True
        assert metrics.total_scenes == 1

    def test_title_not_at_start(self):
        output = {
            "scenes": [
                {"scene_number": 1, "category": "DEFAULT"},
                {"scene_number": 2, "category": "TITLE"}
            ]
        }
        metrics = analyze_classifier_output(output)
        assert metrics.title_at_start is False
        assert "TITLE not at first scene" in metrics.issues

    def test_section_tracking(self):
        output = {
            "scenes": [
                {"scene_number": 1, "category": "TITLE"},
                {"scene_number": 2, "category": "DEFAULT"},
                {"scene_number": 3, "category": "SECTION"},
                {"scene_number": 4, "category": "DEFAULT"},
                {"scene_number": 5, "category": "SECTION"},
            ]
        }
        metrics = analyze_classifier_output(output)
        assert metrics.section_positions == [3, 5]

    def test_distribution_calculation(self):
        output = {
            "scenes": [
                {"scene_number": 1, "category": "TITLE"},
                {"scene_number": 2, "category": "DEFAULT"},
                {"scene_number": 3, "category": "DEFAULT"},
                {"scene_number": 4, "category": "DEFAULT"},
            ]
        }
        metrics = analyze_classifier_output(output)
        assert metrics.distribution["TITLE"] == 0.25
        assert metrics.distribution["DEFAULT"] == 0.75

    def test_all_categories_triggered(self):
        output = {
            "scenes": [
                {"scene_number": 1, "category": "TITLE"},
                {"scene_number": 2, "category": "SECTION"},
                {"scene_number": 3, "category": "LIST"},
                {"scene_number": 4, "category": "NUMBER"},
                {"scene_number": 5, "category": "QUOTE"},
                {"scene_number": 6, "category": "EMPHASIS"},
                {"scene_number": 7, "category": "DEFAULT"},
            ]
        }
        metrics = analyze_classifier_output(output)
        assert len(metrics.categories_triggered) == 7

    def test_unknown_category_defaults(self):
        output = {
            "scenes": [
                {"scene_number": 1, "category": "UNKNOWN_TYPE"}
            ]
        }
        metrics = analyze_classifier_output(output)
        assert "Unknown category" in metrics.issues[0]


class TestCheckSectionSpacing:
    """Tests for section spacing validation."""

    def test_no_sections_short_script(self):
        ok, issues = check_section_spacing([], total_scenes=10)
        assert ok is True
        assert len(issues) == 0

    def test_no_sections_long_script(self):
        ok, issues = check_section_spacing([], total_scenes=20)
        assert ok is False
        assert "No SECTION scenes" in issues[0]

    def test_good_spacing(self):
        # Sections at 5, 15, 25 in a 30-scene script
        ok, issues = check_section_spacing([5, 15, 25], total_scenes=30)
        assert ok is True

    def test_large_gap(self):
        # Section only at position 5, then nothing until end (20 scenes)
        ok, issues = check_section_spacing([5], total_scenes=25)
        assert ok is False
        assert "Large gaps" in issues[0]


class TestCheckDistributionAlignment:
    """Tests for distribution alignment validation."""

    def test_perfect_distribution(self):
        distribution = {
            "TITLE": 0.07,
            "SECTION": 0.12,
            "LIST": 0.17,
            "NUMBER": 0.12,
            "QUOTE": 0.12,
            "EMPHASIS": 0.07,
            "DEFAULT": 0.40,
        }
        ok, issues = check_distribution_alignment(distribution)
        assert ok is True
        assert len(issues) == 0

    def test_heavy_default_skew(self):
        distribution = {
            "TITLE": 0.05,
            "SECTION": 0.05,
            "LIST": 0.05,
            "NUMBER": 0.05,
            "QUOTE": 0.05,
            "EMPHASIS": 0.05,
            "DEFAULT": 0.70,
        }
        ok, issues = check_distribution_alignment(distribution)
        assert "DEFAULT overrepresented" in str(issues)

    def test_missing_categories(self):
        distribution = {
            "TITLE": 0.0,
            "SECTION": 0.0,
            "LIST": 0.0,
            "NUMBER": 0.0,
            "QUOTE": 0.0,
            "EMPHASIS": 0.0,
            "DEFAULT": 1.0,
        }
        ok, issues = check_distribution_alignment(distribution)
        assert ok is False
        # Many underrepresented categories


class TestComputeScore:
    """Tests for score computation logic."""

    def test_score_5_ideal(self):
        metrics = AnalysisMetrics()
        metrics.categories_triggered = set(CATEGORIES)  # All 7
        metrics.title_at_start = True
        metrics.section_positions = [5, 15]
        metrics.total_scenes = 20
        metrics.distribution = {
            "TITLE": 0.07, "SECTION": 0.12, "LIST": 0.17,
            "NUMBER": 0.12, "QUOTE": 0.12, "EMPHASIS": 0.07, "DEFAULT": 0.40
        }

        score = compute_score(metrics)
        assert score == 5

    def test_score_4_good(self):
        metrics = AnalysisMetrics()
        metrics.categories_triggered = {"TITLE", "SECTION", "LIST", "NUMBER", "DEFAULT"}  # 5
        metrics.title_at_start = True
        metrics.section_positions = [5]
        metrics.total_scenes = 10
        metrics.distribution = {
            "TITLE": 0.10, "SECTION": 0.10, "LIST": 0.20,
            "NUMBER": 0.10, "QUOTE": 0.0, "EMPHASIS": 0.0, "DEFAULT": 0.50
        }

        score = compute_score(metrics)
        assert score == 4

    def test_score_3_moderate(self):
        metrics = AnalysisMetrics()
        metrics.categories_triggered = {"TITLE", "SECTION", "LIST", "DEFAULT"}  # 4
        metrics.title_at_start = True
        metrics.section_positions = []
        metrics.total_scenes = 10
        metrics.distribution = {
            "TITLE": 0.10, "SECTION": 0.10, "LIST": 0.20,
            "NUMBER": 0.0, "QUOTE": 0.0, "EMPHASIS": 0.0, "DEFAULT": 0.60
        }

        score = compute_score(metrics)
        assert score == 3

    def test_score_2_poor(self):
        metrics = AnalysisMetrics()
        metrics.categories_triggered = {"TITLE", "SECTION", "DEFAULT"}  # 3
        metrics.title_at_start = True
        metrics.section_positions = []
        metrics.total_scenes = 10
        metrics.distribution = {
            "TITLE": 0.10, "SECTION": 0.10, "LIST": 0.0,
            "NUMBER": 0.0, "QUOTE": 0.0, "EMPHASIS": 0.0, "DEFAULT": 0.50
        }

        score = compute_score(metrics)
        assert score == 2

    def test_score_1_very_poor(self):
        metrics = AnalysisMetrics()
        metrics.categories_triggered = {"DEFAULT"}  # 1
        metrics.title_at_start = False
        metrics.section_positions = []
        metrics.total_scenes = 10
        metrics.distribution = {
            "TITLE": 0.0, "SECTION": 0.0, "LIST": 0.0,
            "NUMBER": 0.0, "QUOTE": 0.0, "EMPHASIS": 0.0, "DEFAULT": 1.0
        }

        score = compute_score(metrics)
        assert score == 1


class TestScoreFromAnalysis:
    """Tests for scoring from pre-computed classifier output."""

    def test_good_script(self):
        classifier_output = {
            "scenes": [
                {"scene_number": 1, "category": "TITLE"},
                {"scene_number": 2, "category": "DEFAULT"},
                {"scene_number": 3, "category": "LIST"},
                {"scene_number": 4, "category": "NUMBER"},
                {"scene_number": 5, "category": "SECTION"},
                {"scene_number": 6, "category": "DEFAULT"},
                {"scene_number": 7, "category": "QUOTE"},
                {"scene_number": 8, "category": "DEFAULT"},
                {"scene_number": 9, "category": "LIST"},
                {"scene_number": 10, "category": "EMPHASIS"},
            ]
        }
        result = score_template_compatibility_from_analysis(classifier_output)

        assert result.score >= 4  # Good coverage
        assert result.title_at_start is True
        assert result.category_count >= 6

    def test_all_default_script(self):
        classifier_output = {
            "scenes": [
                {"scene_number": i, "category": "DEFAULT"}
                for i in range(1, 11)
            ]
        }
        result = score_template_compatibility_from_analysis(classifier_output)

        assert result.score == 1
        assert result.category_count == 1
        assert result.title_at_start is False

    def test_result_contains_raw_response(self):
        classifier_output = {"scenes": [{"scene_number": 1, "category": "TITLE"}]}
        result = score_template_compatibility_from_analysis(classifier_output)

        assert result.raw_response == classifier_output


class TestRealWorldClassifierOutput:
    """Tests using realistic classifier output from the spec example."""

    @pytest.fixture
    def quantum_computing_output(self):
        """The example output from the spec."""
        return {
            "scenes": [
                {"scene_number": 1, "category": "TITLE"},
                {"scene_number": 2, "category": "DEFAULT"},
                {"scene_number": 3, "category": "DEFAULT"},
                {"scene_number": 4, "category": "SECTION"},
                {"scene_number": 5, "category": "NUMBER"},
                {"scene_number": 6, "category": "DEFAULT"},
                {"scene_number": 7, "category": "LIST"},
                {"scene_number": 8, "category": "NUMBER"},
                {"scene_number": 9, "category": "NUMBER"},
                {"scene_number": 10, "category": "QUOTE"},
                {"scene_number": 11, "category": "LIST"},
                {"scene_number": 12, "category": "NUMBER"},
                {"scene_number": 13, "category": "NUMBER"},
                {"scene_number": 14, "category": "LIST"},
                {"scene_number": 15, "category": "DEFAULT"},
                {"scene_number": 16, "category": "QUOTE"},
                {"scene_number": 17, "category": "SECTION"},
                {"scene_number": 18, "category": "DEFAULT"},
                {"scene_number": 19, "category": "NUMBER"},
                {"scene_number": 20, "category": "EMPHASIS"},
            ]
        }

    def test_quantum_computing_example(self, quantum_computing_output):
        result = score_template_compatibility_from_analysis(quantum_computing_output)

        # This is a well-structured script from the spec
        assert result.score >= 4
        assert result.title_at_start is True
        assert "TITLE" in result.categories_triggered
        assert "SECTION" in result.categories_triggered
        assert "NUMBER" in result.categories_triggered
        assert "LIST" in result.categories_triggered
        assert "QUOTE" in result.categories_triggered
        assert "EMPHASIS" in result.categories_triggered
        assert "DEFAULT" in result.categories_triggered
        assert result.category_count == 7
