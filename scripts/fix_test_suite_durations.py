"""
Fix duration parsing in existing test_suite.json.

The original parser had a bug: "30s" was being parsed as 30 minutes (1800 sec)
instead of 30 seconds because the regex didn't match the "s" suffix.

Run with: python scripts/fix_test_suite_durations.py
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TEST_SUITE_PATH = PROJECT_ROOT / "data" / "test_suite.json"
BACKUP_PATH = PROJECT_ROOT / "data" / "test_suite_backup.json"


def parse_duration_to_seconds(duration_range: str) -> dict:
    """
    Parse duration range like '1min - 5min' into min/max seconds.

    Fixed version that properly handles:
    - "30s" -> 30 seconds (not 1800!)
    - "30s - 1min" -> 30 to 60 seconds
    - "1min - 5min" -> 60 to 300 seconds
    - "> 5min" -> 300+ seconds
    """
    if not duration_range:
        return {"min_sec": None, "max_sec": None}

    result = {"min_sec": None, "max_sec": None}

    # Normalize
    duration = duration_range.lower().strip()

    # Pattern: number + optional unit (s, sec, second, seconds, m, min, minute, minutes)
    numbers = re.findall(r"(\d+)\s*(s(?:ec(?:ond)?s?)?|m(?:in(?:ute)?s?)?)?", duration)

    # Filter out empty matches
    numbers = [(val, unit) for val, unit in numbers if val]

    def to_seconds(val: str, unit: str) -> int:
        """Convert value with unit to seconds."""
        val = int(val)
        if not unit:
            # No unit - default to minutes for ambiguous cases
            return val * 60
        unit = unit.lower()
        # Check for seconds: s, sec, second, seconds
        if unit.startswith('s'):
            return val
        # Otherwise minutes: m, min, minute, minutes
        return val * 60

    if len(numbers) >= 2:
        val1, unit1 = numbers[0]
        val2, unit2 = numbers[1]

        result["min_sec"] = to_seconds(val1, unit1)
        result["max_sec"] = to_seconds(val2, unit2)

        # Ensure min <= max
        if result["min_sec"] > result["max_sec"]:
            result["min_sec"], result["max_sec"] = result["max_sec"], result["min_sec"]

    elif len(numbers) == 1:
        val, unit = numbers[0]
        sec = to_seconds(val, unit)
        result["min_sec"] = sec
        result["max_sec"] = sec

    # Handle "> X" case (e.g., "> 5min" = at least 300 seconds)
    if ">" in duration and result["min_sec"] is not None:
        result["max_sec"] = 3600  # 1 hour upper bound

    # Handle "< X" case (e.g., "< 1min" = up to 60 seconds)
    if "<" in duration and result["max_sec"] is not None:
        result["min_sec"] = 0

    return result


def main():
    print("=" * 60)
    print("Fixing Test Suite Duration Parsing")
    print("=" * 60)

    if not TEST_SUITE_PATH.exists():
        print(f"[ERROR] Test suite not found: {TEST_SUITE_PATH}")
        return

    # Load test suite
    with open(TEST_SUITE_PATH, "r", encoding="utf-8") as f:
        test_suite = json.load(f)

    print(f"Loaded {len(test_suite)} records from test_suite.json")

    # Backup original
    with open(BACKUP_PATH, "w", encoding="utf-8") as f:
        json.dump(test_suite, f, indent=2, ensure_ascii=False)
    print(f"[BACKUP] Saved to {BACKUP_PATH}")

    # Fix each record
    fixed_count = 0
    for record in test_suite:
        duration_range = record.get("duration_range")
        if not duration_range:
            continue

        old_min = record.get("duration_min_sec")
        old_max = record.get("duration_max_sec")

        parsed = parse_duration_to_seconds(duration_range)
        new_min = parsed["min_sec"]
        new_max = parsed["max_sec"]

        if old_min != new_min or old_max != new_max:
            print(f"  [{record['id'][:8]}...] {duration_range}")
            print(f"    OLD: min={old_min}s, max={old_max}s")
            print(f"    NEW: min={new_min}s, max={new_max}s")
            record["duration_min_sec"] = new_min
            record["duration_max_sec"] = new_max
            fixed_count += 1

    # Save fixed test suite
    with open(TEST_SUITE_PATH, "w", encoding="utf-8") as f:
        json.dump(test_suite, f, indent=2, ensure_ascii=False)

    print(f"\n[FIXED] {fixed_count} records updated")
    print(f"[SAVED] {TEST_SUITE_PATH}")

    print("\n" + "=" * 60)
    print("DURATION FIX COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
