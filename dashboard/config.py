"""Dashboard configuration - paths, constants, display names."""

from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RUNS_DIR = DATA_DIR / "runs"

# Scoring dimensions
SCRIPT_QUALITY_DIMENSIONS = [
    "hook_quality",
    "tone_match",
    "structural_flow",
    "content_richness",
    "completeness",
]

SYSTEM_METRIC_DIMENSIONS = [
    "timing_accuracy",
    "template_compatibility",
]

ALL_DIMENSIONS = SCRIPT_QUALITY_DIMENSIONS + SYSTEM_METRIC_DIMENSIONS

# Display names for dimensions
DIMENSION_NAMES = {
    "hook_quality": "Hook Quality",
    "tone_match": "Tone Match",
    "structural_flow": "Structural Flow",
    "content_richness": "Content Richness",
    "completeness": "Completeness",
    "timing_accuracy": "Timing Accuracy",
    "template_compatibility": "Template Compatibility",
}

# Colors
COLORS = {
    "primary": "#FF6B6B",
    "secondary": "#4ECDC4",
    "success": "#2ECC71",
    "warning": "#F39C12",
    "danger": "#E74C3C",
    "info": "#3498DB",
}

# Classification colors
CLASSIFICATION_COLORS = {
    "IMPROVED": "#2ECC71",
    "REGRESSION": "#E74C3C",
    "NO_CHANGE": "#95A5A6",
}

# Video types
VIDEO_TYPES = [
    "Explainer",
    "Marketing",
    "Tutorial",
    "Communications",
    "Showcase",
]

# Duration ranges
DURATION_RANGES = [
    "30s",
    "30s - 1min",
    "1min",
    "1min - 5min",
    "> 5min",
    "Unknown",
]

# Platforms
PLATFORMS = [
    "YouTube",
    "YouTube Shorts",
    "Instagram Reels",
    "Instagram Feed",
    "TikTok",
    "Facebook Reels",
    "Facebook Feed",
    "Twitter/X Video",
    "Website",
    "Internal Company",
    "Unknown",
]
