"""
Parse downloaded samples and extract eval-relevant fields.

Outputs:
- data/parsed_records.json  (full data with scripts)
- data/parsed_records.csv   (summary table for quick viewing)
"""

import json
import csv
import re
from pathlib import Path
from collections import Counter
from langdetect import detect, LangDetectException

SAMPLES_DIR = Path(__file__).parent.parent / "data" / "samples"
OUTPUT_DIR = Path(__file__).parent.parent / "data"

# Estimated reading speed for video scripts (words per minute)
WPM = 140

# Emoji pattern for removal
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"  # misc
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA00-\U0001FA6F"  # chess symbols
    "\U0001FA70-\U0001FAFF"  # symbols extended
    "\U00002600-\U000026FF"  # misc symbols
    "]+",
    flags=re.UNICODE
)


def remove_emojis(text: str) -> str:
    """Remove emojis from text."""
    if not text:
        return text
    return EMOJI_PATTERN.sub("", text).strip()


def is_english(text: str, min_length: int = 20) -> bool:
    """Check if text is English using langdetect."""
    if not text or len(text) < min_length:
        return False
    try:
        return detect(text) == "en"
    except LangDetectException:
        return False


def is_english_subject(subject: str) -> bool:
    """Check if subject is English."""
    if not subject:
        return False  # Null subjects should be filtered out

    subject_stripped = subject.strip()

    # Check for non-Latin characters (Thai, Chinese, Arabic, Cyrillic, etc.)
    # These are definitely not English
    def has_non_latin_script(text):
        for c in text:
            code = ord(c)
            # Allow Basic Latin (0-127), Latin Extended (128-687), some punctuation
            # Reject if character is clearly from non-Latin script
            if code > 687 and code < 0x2000:  # Skip punctuation/symbols range
                return True
            if code >= 0x0600 and code <= 0x06FF:  # Arabic
                return True
            if code >= 0x0E00 and code <= 0x0E7F:  # Thai
                return True
            if code >= 0x4E00 and code <= 0x9FFF:  # CJK (Chinese/Japanese/Korean)
                return True
            if code >= 0x0400 and code <= 0x04FF:  # Cyrillic
                return True
            if code >= 0xAC00 and code <= 0xD7AF:  # Korean Hangul
                return True
            if code >= 0x3040 and code <= 0x309F:  # Hiragana
                return True
            if code >= 0x30A0 and code <= 0x30FF:  # Katakana
                return True
        return False

    if has_non_latin_script(subject_stripped):
        return False  # Non-Latin script is not English

    # Check for non-English accented characters common in Spanish/Portuguese/Italian/German/French
    non_english_chars = set('áéíóúñüöäàèìòùçãõâêîôûëïÿœæ')
    has_non_english_chars = any(c.lower() in non_english_chars for c in subject_stripped)

    # If has non-English accented chars, must pass language detection
    if has_non_english_chars:
        try:
            return detect(subject_stripped) == "en"
        except LangDetectException:
            return False  # If can't detect and has foreign chars, reject

    # For short ASCII-only subjects (< 20 chars), assume English
    if len(subject_stripped) < 20:
        return True

    # For longer subjects, run language detection
    try:
        return detect(subject_stripped) == "en"
    except LangDetectException:
        return True  # If detection fails on ASCII text, assume English


def extract_video_type(system_prompt: str) -> str:
    """Extract video type from system prompt first line."""
    video_types = {
        "explainer": "Explainer",
        "marketing": "Marketing",
        "internal comms": "Internal Comms",
        "tutorial": "Tutorial",
        "product intro": "Product Intro",
        "showcase": "Showcase",
        "promotional": "Promotional",
    }

    system_lower = system_prompt.lower()

    for key, value in video_types.items():
        if key in system_lower:
            return value

    # Fallback: try to find "X video script" pattern
    match = re.search(r"(\w+)\s+video\s+script", system_lower)
    if match:
        return match.group(1).title()

    return "Unknown"


def extract_from_user_prompt(user_content: str) -> dict:
    """Extract subject, duration, platform from user prompt."""
    result = {
        "subject": None,
        "duration_range": None,
        "platform": None,
    }

    # Extract subject: {value}
    subject_match = re.search(r"subject:\s*\{([^}]+)\}", user_content, re.IGNORECASE)
    if subject_match:
        result["subject"] = subject_match.group(1).strip()

    # Extract duration: {value}
    duration_match = re.search(r"duration:\s*\{([^}]+)\}", user_content, re.IGNORECASE)
    if duration_match:
        result["duration_range"] = duration_match.group(1).strip()

    # Extract platform: {value}
    platform_match = re.search(r"platform\s*:\s*\{([^}]+)\}", user_content, re.IGNORECASE)
    if platform_match:
        result["platform"] = platform_match.group(1).strip()

    return result


def parse_duration_to_seconds(duration_range: str) -> dict:
    """Parse duration range like '1min - 5min' into min/max seconds."""
    if not duration_range:
        return {"min_sec": None, "max_sec": None, "midpoint_sec": None}

    # Pattern: Xmin - Ymin or X-Y min or similar
    # Examples: "1min - 5min", "30sec - 1min", "2-3 minutes", "30s", "> 5min"

    result = {"min_sec": None, "max_sec": None, "midpoint_sec": None}

    # Normalize
    duration = duration_range.lower().strip()

    # Try to find numbers with units
    # Pattern: number + optional unit (supports: s, sec, second, seconds, m, min, minute, minutes)
    # The 's' must be captured separately since it's a single character
    numbers = re.findall(r"(\d+)\s*(s(?:ec(?:ond)?s?)?|m(?:in(?:ute)?s?)?)?", duration)

    # Filter out empty matches
    numbers = [(val, unit) for val, unit in numbers if val]

    def to_seconds(val: str, unit: str) -> int:
        """Convert value with unit to seconds."""
        val = int(val)
        if not unit:
            # No unit - check context
            # If value is small (<=10), likely minutes; if larger, could be seconds
            # But safer to default to minutes for ambiguous cases
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

        result["midpoint_sec"] = (result["min_sec"] + result["max_sec"]) // 2

    elif len(numbers) == 1:
        val, unit = numbers[0]
        sec = to_seconds(val, unit)
        result["min_sec"] = sec
        result["max_sec"] = sec
        result["midpoint_sec"] = sec

    # Handle special cases like "> 5min" (greater than)
    if ">" in duration and result["min_sec"] is not None:
        # For "> X", min stays at X, max is unlimited (use 1 hour as practical upper bound)
        result["max_sec"] = 3600  # 1 hour

    # Handle special cases like "< 1min" (less than)
    if "<" in duration and result["max_sec"] is not None:
        # For "< X", min is 0, max stays at X
        result["min_sec"] = 0

    return result


def count_words(text: str) -> int:
    """Count words in text."""
    if not text:
        return 0
    return len(text.split())


def estimate_duration_sec(word_count: int) -> float:
    """Estimate script duration in seconds based on word count at 140 WPM."""
    if not word_count:
        return 0.0
    return round((word_count / WPM) * 60, 1)


def parse_sample_file(filepath: Path) -> dict:
    """Parse a single sample JSON file and extract all relevant fields."""
    with open(filepath, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Extract ID from filename
    record_id = filepath.stem

    # Check for errors
    if raw.get("error"):
        return {
            "id": record_id,
            "error": str(raw["error"]),
            "valid": False,
        }

    data = raw.get("data", {})
    prompt = data.get("prompt", [])

    # Extract system and user prompts
    system_prompt = ""
    user_prompt = ""

    for msg in prompt:
        if msg.get("role") == "system":
            system_prompt = msg.get("content", "")
        elif msg.get("role") == "user":
            user_prompt = msg.get("content", "")

    # Extract fields
    video_type = extract_video_type(system_prompt)
    user_fields = extract_from_user_prompt(user_prompt)
    duration_parsed = parse_duration_to_seconds(user_fields["duration_range"])

    script = data.get("chunk", "")

    # Remove emojis from subject and script
    subject = remove_emojis(user_fields["subject"]) if user_fields["subject"] else None
    script = remove_emojis(script)

    word_count = count_words(script)
    char_count = len(script) if script else 0
    estimated_time_sec = estimate_duration_sec(word_count)

    # Check if script is English
    script_english = is_english(script)

    # Check if subject exists and is English
    subject_valid = subject is not None and len(subject.strip()) > 0
    subject_english = is_english_subject(subject) if subject_valid else False

    # Both script and subject must be English (and subject must exist)
    english = script_english and subject_valid and subject_english

    return {
        "id": record_id,
        "valid": True,
        "english": english,
        "subject_valid": subject_valid,
        "subject_english": subject_english,
        "script_english": script_english,
        "video_type": video_type,
        "subject": subject,
        "duration_range": user_fields["duration_range"],
        "duration_min_sec": duration_parsed["min_sec"],
        "duration_max_sec": duration_parsed["max_sec"],
        "duration_midpoint_sec": duration_parsed["midpoint_sec"],
        "platform": user_fields["platform"],
        "script": script,
        "word_count": word_count,
        "char_count": char_count,
        "estimated_time_sec": estimated_time_sec,
        "system_prompt": system_prompt,  # Keep for catalog
    }


def main():
    print("=" * 60)
    print("Parsing Sample Records")
    print("=" * 60)

    # Find all JSON files in samples directory
    sample_files = list(SAMPLES_DIR.glob("*.json"))
    print(f"Found {len(sample_files)} sample files\n")

    if not sample_files:
        print("No sample files found. Run explore_s3_data.py first.")
        return

    # Parse all files
    all_records = []
    errors = []
    filtered_out = {
        "non_english_script": [],
        "null_subject": [],
        "non_english_subject": [],
    }

    for filepath in sample_files:
        try:
            record = parse_sample_file(filepath)
            if record.get("valid"):
                if record.get("english"):
                    all_records.append(record)
                else:
                    # Track why it was filtered
                    if not record.get("script_english"):
                        filtered_out["non_english_script"].append(record)
                    elif not record.get("subject_valid"):
                        filtered_out["null_subject"].append(record)
                    elif not record.get("subject_english"):
                        filtered_out["non_english_subject"].append(record)
            else:
                errors.append(record)
        except Exception as e:
            errors.append({"id": filepath.stem, "error": str(e), "valid": False})
            print(f"[ERR] {filepath.name}: {e}")

    records = all_records
    total_filtered = sum(len(v) for v in filtered_out.values())
    print(f"Parsed: {len(records)} valid English records")
    print(f"Filtered out: {total_filtered} total")
    print(f"  - Non-English script: {len(filtered_out['non_english_script'])}")
    print(f"  - Null subject: {len(filtered_out['null_subject'])}")
    print(f"  - Non-English subject: {len(filtered_out['non_english_subject'])}")
    print(f"  - Errors: {len(errors)}\n")

    # Print summary statistics
    print("--- Summary Statistics ---")
    print(f"Total valid records: {len(records)}")

    # Video type distribution
    video_types = Counter(r["video_type"] for r in records)
    print(f"\nVideo Types:")
    for vt, count in video_types.most_common():
        print(f"  {vt}: {count}")

    # Platform distribution
    platforms = Counter(r["platform"] for r in records if r["platform"])
    print(f"\nPlatforms:")
    for p, count in platforms.most_common():
        print(f"  {p}: {count}")

    # Duration distribution
    durations = Counter(r["duration_range"] for r in records if r["duration_range"])
    print(f"\nDuration Ranges:")
    for d, count in durations.most_common():
        print(f"  {d}: {count}")

    # Word count stats
    word_counts = [r["word_count"] for r in records]
    if word_counts:
        print(f"\nScript Word Counts:")
        print(f"  Min: {min(word_counts)}")
        print(f"  Max: {max(word_counts)}")
        print(f"  Avg: {sum(word_counts) // len(word_counts)}")

    # Estimated time stats
    est_times = [r["estimated_time_sec"] for r in records]
    if est_times:
        print(f"\nEstimated Duration (at {WPM} WPM):")
        print(f"  Min: {min(est_times):.1f}s ({min(est_times)/60:.1f}min)")
        print(f"  Max: {max(est_times):.1f}s ({max(est_times)/60:.1f}min)")
        print(f"  Avg: {sum(est_times)/len(est_times):.1f}s ({sum(est_times)/len(est_times)/60:.1f}min)")

    # Save JSON (full data including scripts)
    json_path = OUTPUT_DIR / "parsed_records.json"
    # Remove internal fields from JSON output
    internal_fields = {"system_prompt", "subject_valid", "subject_english", "script_english"}
    json_records = [{k: v for k, v in r.items() if k not in internal_fields} for r in records]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_records, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {json_path}")

    # Save CSV (summary without full script text)
    csv_path = OUTPUT_DIR / "parsed_records.csv"
    csv_fields = [
        "id", "video_type", "subject", "duration_range",
        "duration_min_sec", "duration_max_sec", "duration_midpoint_sec",
        "platform", "word_count", "char_count", "estimated_time_sec"
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    print(f"Saved: {csv_path}")

    # Generate system prompt catalog
    unique_prompts = {}
    for r in records:
        prompt_hash = hash(r["system_prompt"][:200])  # Hash first 200 chars
        if prompt_hash not in unique_prompts:
            unique_prompts[prompt_hash] = {
                "video_type": r["video_type"],
                "prompt": r["system_prompt"],
                "count": 1
            }
        else:
            unique_prompts[prompt_hash]["count"] += 1

    catalog_path = OUTPUT_DIR / "system-prompts-catalog.md"
    with open(catalog_path, "w", encoding="utf-8") as f:
        f.write("# System Prompts Catalog\n\n")
        f.write(f"*Found {len(unique_prompts)} unique system prompt variants*\n\n")
        f.write("---\n\n")

        for i, (_, info) in enumerate(unique_prompts.items(), 1):
            f.write(f"## Variant {i}: {info['video_type']} ({info['count']} occurrences)\n\n")
            f.write("```\n")
            f.write(info["prompt"][:2000])  # Truncate very long prompts
            if len(info["prompt"]) > 2000:
                f.write("\n... [truncated]")
            f.write("\n```\n\n---\n\n")

    print(f"Saved: {catalog_path}")

    print("\n" + "=" * 60)
    print("PARSING COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
