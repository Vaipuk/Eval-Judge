"""
Build Test Suite for Evaluation Pipeline.

Reads data/parsed_records.json and curates a stratified test suite:
- Strips generated scripts, keeps only input fields
- Stratifies across video types (aim for 15-20 per type)
- Diversifies across duration ranges and platforms
- Deduplicates near-identical subjects
- Flags coverage gaps

Outputs:
- data/test_suite.json — curated test inputs
- data/test_suite_stats.md — distribution summary

Run with: python -m scripts.build_test_suite
"""

import json
import re
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime
from difflib import SequenceMatcher

PROJECT_ROOT = Path(__file__).parent.parent
INPUT_PATH = PROJECT_ROOT / "data" / "parsed_records.json"
OUTPUT_JSON = PROJECT_ROOT / "data" / "test_suite.json"
OUTPUT_STATS = PROJECT_ROOT / "data" / "test_suite_stats.md"

# Target video types from the spec
TARGET_VIDEO_TYPES = ["Explainer", "Marketing", "Internal Comms", "Tutorial", "Product Intro"]

# Fields to keep in test suite (strip generated scripts)
OUTPUT_FIELDS = ["id", "video_type", "subject", "duration_range", "duration_min_sec", "duration_max_sec", "platform"]

# Target records per video type
TARGET_PER_TYPE = 20
MIN_PER_TYPE = 15

# Fields to check for completeness (higher score = more complete)
COMPLETENESS_FIELDS = ["duration_range", "duration_min_sec", "duration_max_sec", "platform"]


def field_completeness_score(record: dict) -> int:
    """
    Calculate completeness score for a record.
    Higher score means more fields are filled out.
    """
    score = 0
    for field in COMPLETENESS_FIELDS:
        if record.get(field) is not None:
            score += 1
    return score


def sort_by_completeness(records: list) -> list:
    """
    Sort records by completeness score (most complete first).
    This ensures we prioritize samples with all fields filled out.
    """
    return sorted(records, key=lambda r: field_completeness_score(r), reverse=True)


def normalize_subject(subject: str) -> str:
    """Normalize subject string for comparison."""
    if not subject:
        return ""
    # Lowercase, remove extra whitespace, remove quotes
    normalized = subject.lower().strip()
    normalized = re.sub(r'["\']', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized


def subject_similarity(s1: str, s2: str) -> float:
    """Calculate similarity ratio between two subjects."""
    if not s1 or not s2:
        return 0.0
    n1 = normalize_subject(s1)
    n2 = normalize_subject(s2)
    return SequenceMatcher(None, n1, n2).ratio()


def deduplicate_subjects(records: list, threshold: float = 0.85) -> list:
    """
    Remove records with near-duplicate subjects.
    Keeps the first occurrence when duplicates are found.
    """
    unique_records = []
    seen_subjects = []

    for record in records:
        subject = record.get("subject", "")
        is_duplicate = False

        for seen in seen_subjects:
            if subject_similarity(subject, seen) >= threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            unique_records.append(record)
            if subject:
                seen_subjects.append(subject)

    return unique_records


def stratify_within_type(records: list, target: int) -> list:
    """
    Select records from a video type with diversity across duration and platform.
    Uses round-robin sampling across strata.
    Records are assumed to be pre-sorted by completeness.

    Priority:
    1. First exhaust strata with complete records (both duration and platform known)
    2. Then strata with partial records (one field known)
    3. Finally strata with no fields known
    """
    if len(records) <= target:
        return records

    # Group by (duration_range, platform) for stratification
    # Maintain order within each stratum (most complete first since input is pre-sorted)
    strata = defaultdict(list)
    for r in records:
        key = (r.get("duration_range") or "unknown", r.get("platform") or "unknown")
        strata[key].append(r)

    # Separate strata into tiers by completeness
    complete_strata = []  # Both fields known
    partial_strata = []   # One field known
    empty_strata = []     # Both unknown

    for key in strata.keys():
        duration, platform = key
        unknown_count = (1 if duration == "unknown" else 0) + (1 if platform == "unknown" else 0)
        if unknown_count == 0:
            complete_strata.append(key)
        elif unknown_count == 1:
            partial_strata.append(key)
        else:
            empty_strata.append(key)

    selected = []

    # Process each tier in order, using round-robin within each tier
    for tier_keys in [complete_strata, partial_strata, empty_strata]:
        if len(selected) >= target:
            break
        if not tier_keys:
            continue

        tier_keys = list(tier_keys)  # Make a copy
        idx = 0

        # Round-robin within this tier until exhausted or target reached
        while len(selected) < target and tier_keys:
            key = tier_keys[idx % len(tier_keys)]
            if strata[key]:
                selected.append(strata[key].pop(0))

            # Remove empty strata from this tier
            tier_keys = [k for k in tier_keys if strata[k]]
            if tier_keys:
                idx = (idx + 1) % len(tier_keys) if tier_keys else 0

    return selected


def build_test_suite(records: list) -> tuple[list, dict]:
    """
    Build the test suite with stratification and deduplication.
    Returns (test_suite, stats_dict).

    Note: Input records are already filtered by parse_samples.py to have:
    - English scripts
    - Non-null English subjects
    """
    stats = {
        "total_input": len(records),
        "by_video_type": {},
        "by_duration_range": Counter(),
        "by_platform": Counter(),
        "coverage_gaps": [],
        "low_coverage_types": [],
    }

    # Group records by video type
    by_type = defaultdict(list)
    for r in records:
        by_type[r.get("video_type", "Unknown")].append(r)

    test_suite = []

    # Process each target video type
    for video_type in TARGET_VIDEO_TYPES:
        type_records = by_type.get(video_type, [])
        original_count = len(type_records)

        if original_count == 0:
            stats["coverage_gaps"].append(video_type)
            stats["by_video_type"][video_type] = {
                "available": 0,
                "selected": 0,
                "after_dedup": 0,
            }
            continue

        # Step 1: Sort by completeness (most complete first)
        # This ensures we keep records with all fields filled when deduplicating
        sorted_records = sort_by_completeness(type_records)

        # Step 2: Deduplicate subjects (keeps first occurrence, which is most complete)
        deduped = deduplicate_subjects(sorted_records)

        # Step 3: Stratify and select
        selected = stratify_within_type(deduped, TARGET_PER_TYPE)

        # Track stats
        stats["by_video_type"][video_type] = {
            "available": original_count,
            "after_dedup": len(deduped),
            "selected": len(selected),
        }

        if len(selected) < MIN_PER_TYPE:
            stats["low_coverage_types"].append((video_type, len(selected)))

        # Add to test suite (strip to output fields only)
        for r in selected:
            test_input = {field: r.get(field) for field in OUTPUT_FIELDS}
            test_suite.append(test_input)

    # Handle any video types not in TARGET_VIDEO_TYPES but present in data
    other_types = set(by_type.keys()) - set(TARGET_VIDEO_TYPES)
    for video_type in other_types:
        type_records = by_type[video_type]
        sorted_records = sort_by_completeness(type_records)
        deduped = deduplicate_subjects(sorted_records)
        selected = stratify_within_type(deduped, TARGET_PER_TYPE)

        stats["by_video_type"][video_type] = {
            "available": len(type_records),
            "after_dedup": len(deduped),
            "selected": len(selected),
            "note": "Not a target type in spec",
        }

        for r in selected:
            test_input = {field: r.get(field) for field in OUTPUT_FIELDS}
            test_suite.append(test_input)

    # Aggregate stats
    for r in test_suite:
        stats["by_duration_range"][r.get("duration_range") or "None"] += 1
        stats["by_platform"][r.get("platform") or "None"] += 1

    stats["total_selected"] = len(test_suite)

    return test_suite, stats


def generate_stats_markdown(stats: dict, test_suite: list) -> str:
    """Generate the stats markdown file content."""
    lines = [
        "# Test Suite Statistics",
        "",
        f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Total records in parsed_records.json:** {stats['total_input']}",
        f"- **Records selected for test suite:** {stats['total_selected']}",
        "",
        "---",
        "",
        "## Distribution by Video Type",
        "",
        "| Video Type | Available | After Dedup | Selected | Notes |",
        "|------------|-----------|-------------|----------|-------|",
    ]

    for video_type in TARGET_VIDEO_TYPES + sorted(set(stats["by_video_type"].keys()) - set(TARGET_VIDEO_TYPES)):
        if video_type in stats["by_video_type"]:
            info = stats["by_video_type"][video_type]
            note = info.get("note", "")
            if info["available"] == 0:
                note = "❌ Missing"
            elif info["selected"] < MIN_PER_TYPE:
                note = "⚠️ Low coverage"
            lines.append(
                f"| {video_type} | {info['available']} | {info.get('after_dedup', 'N/A')} | {info['selected']} | {note} |"
            )
        else:
            lines.append(f"| {video_type} | 0 | 0 | 0 | ❌ Missing |")

    lines.extend([
        "",
        "---",
        "",
        "## Distribution by Duration Range",
        "",
        "| Duration Range | Count |",
        "|----------------|-------|",
    ])

    for dr, count in sorted(stats["by_duration_range"].items(), key=lambda x: -x[1]):
        lines.append(f"| {dr} | {count} |")

    lines.extend([
        "",
        "---",
        "",
        "## Distribution by Platform",
        "",
        "| Platform | Count |",
        "|----------|-------|",
    ])

    for p, count in sorted(stats["by_platform"].items(), key=lambda x: -x[1]):
        lines.append(f"| {p} | {count} |")

    # Coverage gaps
    lines.extend([
        "",
        "---",
        "",
        "## Coverage Gaps",
        "",
    ])

    if stats["coverage_gaps"]:
        lines.append("**Missing video types (0 records):**")
        for vt in stats["coverage_gaps"]:
            lines.append(f"- ❌ {vt}")
        lines.append("")

    if stats["low_coverage_types"]:
        lines.append(f"**Low coverage types (< {MIN_PER_TYPE} records):**")
        for vt, count in stats["low_coverage_types"]:
            lines.append(f"- ⚠️ {vt}: only {count} records")
        lines.append("")

    if not stats["coverage_gaps"] and not stats["low_coverage_types"]:
        lines.append("✅ All target video types have adequate coverage.")
        lines.append("")

    # Example entries
    lines.extend([
        "---",
        "",
        "## Example Test Suite Entries",
        "",
        "```json",
    ])

    # Show 3 examples from different video types if possible
    examples = []
    seen_types = set()
    for r in test_suite:
        if r["video_type"] not in seen_types:
            examples.append(r)
            seen_types.add(r["video_type"])
            if len(examples) >= 3:
                break

    lines.append(json.dumps(examples, indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def main():
    print("=" * 60)
    print("Building Test Suite")
    print("=" * 60)

    # Load parsed records
    if not INPUT_PATH.exists():
        print(f"[ERROR] Input file not found: {INPUT_PATH}")
        print("Run parse_samples.py first to generate parsed_records.json")
        return

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)

    print(f"\nLoaded {len(records)} records from {INPUT_PATH.name}")

    # Build test suite
    test_suite, stats = build_test_suite(records)


    # Save test suite JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(test_suite, f, indent=2, ensure_ascii=False)
    print(f"\n[SAVED] Test suite: {OUTPUT_JSON}")
    print(f"        Records: {len(test_suite)}")

    # Generate and save stats markdown
    stats_md = generate_stats_markdown(stats, test_suite)
    with open(OUTPUT_STATS, "w", encoding="utf-8") as f:
        f.write(stats_md)
    print(f"[SAVED] Stats: {OUTPUT_STATS}")

    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUITE SUMMARY")
    print("=" * 60)

    print(f"\nTotal test inputs: {len(test_suite)}")

    print("\nBy Video Type:")
    type_counts = Counter(r["video_type"] for r in test_suite)
    for vt in TARGET_VIDEO_TYPES:
        count = type_counts.get(vt, 0)
        status = "[OK]" if count >= MIN_PER_TYPE else ("[LOW]" if count > 0 else "[MISS]")
        print(f"  {status} {vt}: {count}")

    # Show any additional types
    for vt, count in type_counts.items():
        if vt not in TARGET_VIDEO_TYPES:
            print(f"  + {vt}: {count} (bonus)")

    if stats["coverage_gaps"]:
        print(f"\n[WARN] Missing types: {', '.join(stats['coverage_gaps'])}")

    if stats["low_coverage_types"]:
        print(f"[WARN] Low coverage: {', '.join(f'{vt} ({c})' for vt, c in stats['low_coverage_types'])}")

    print("\n" + "=" * 60)
    print("TEST SUITE BUILD COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
