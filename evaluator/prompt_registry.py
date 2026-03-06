"""
Prompt Registry

JSON-based registry for managing prompt versions.
Supports both unified prompts (single prompt for all video types)
and per-type prompts (separate prompt for each video type).

Registry file: data/prompt_versions.json
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal

PROJECT_ROOT = Path(__file__).parent.parent
REGISTRY_PATH = PROJECT_ROOT / "data" / "prompt_versions.json"

# Valid video types for per-type prompts
VIDEO_TYPES = ["Explainer", "Marketing", "Tutorial", "Internal Comms", "Product Intro"]

# File name mapping for per-type prompt directories
VIDEO_TYPE_FILES = {
    "Explainer": "explainer.txt",
    "Marketing": "marketing.txt",
    "Tutorial": "tutorial.txt",
    "Internal Comms": "internal_comms.txt",
    "Product Intro": "product_intro.txt",
}


def _load_registry() -> dict:
    """Load the prompt registry from JSON file."""
    if not REGISTRY_PATH.exists():
        return {"prompt_versions": []}

    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_registry(registry: dict) -> None:
    """Save the prompt registry to JSON file."""
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)


def get_prompt_entry(prompt_id: str) -> Optional[dict]:
    """
    Get a prompt entry by ID.

    Args:
        prompt_id: The unique identifier for the prompt version

    Returns:
        The prompt entry dict, or None if not found
    """
    registry = _load_registry()
    for entry in registry.get("prompt_versions", []):
        if entry.get("id") == prompt_id:
            return entry
    return None


def get_prompt(prompt_id: str, video_type: Optional[str] = None) -> Optional[str]:
    """
    Get the prompt text for a given prompt version.

    For unified prompts, returns the single prompt.
    For per-type prompts, returns the prompt for the specified video type.

    Args:
        prompt_id: The unique identifier for the prompt version
        video_type: Required for per-type prompts, ignored for unified

    Returns:
        The prompt text, or None if not found

    Raises:
        ValueError: If video_type is required but not provided
    """
    entry = get_prompt_entry(prompt_id)
    if not entry:
        return None

    prompt_type = entry.get("type", "unified")

    if prompt_type == "unified":
        return entry.get("prompt")

    elif prompt_type == "per-type":
        if not video_type:
            raise ValueError(f"video_type is required for per-type prompt '{prompt_id}'")

        prompts = entry.get("prompts", {})
        return prompts.get(video_type)

    else:
        raise ValueError(f"Unknown prompt type: {prompt_type}")


def list_prompts(status: Optional[str] = None) -> list[dict]:
    """
    List all registered prompts, optionally filtered by status.

    Args:
        status: Filter by status (deprecated, baseline, production, draft)

    Returns:
        List of prompt entries
    """
    registry = _load_registry()
    entries = registry.get("prompt_versions", [])

    if status:
        entries = [e for e in entries if e.get("status") == status]

    return entries


def register_prompt(
    prompt_id: str,
    prompt_type: Literal["unified", "per-type"],
    model: str,
    description: str,
    prompt: Optional[str] = None,
    prompts: Optional[dict[str, str]] = None,
    prompt_dir: Optional[Path] = None,
    status: str = "draft",
) -> dict:
    """
    Register a new prompt version.

    Args:
        prompt_id: Unique identifier (e.g., "unified-v2.1", "legacy-v1.0")
        prompt_type: "unified" for single prompt, "per-type" for per-video-type prompts
        model: Model to use for generation (e.g., "gpt-4o-mini", "gpt-4.1-mini")
        description: Human-readable description
        prompt: The prompt text (for unified type)
        prompts: Dict of video_type -> prompt text (for per-type)
        prompt_dir: Directory containing individual prompt files (alternative to prompts dict)
        status: One of "draft", "baseline", "production", "deprecated"

    Returns:
        The created prompt entry

    Raises:
        ValueError: If prompt already exists or required fields missing
    """
    # Check if ID already exists
    if get_prompt_entry(prompt_id):
        raise ValueError(f"Prompt '{prompt_id}' already exists")

    entry = {
        "id": prompt_id,
        "type": prompt_type,
        "model": model,
        "description": description,
        "status": status,
        "date_created": datetime.now().strftime("%Y-%m-%d"),
    }

    if prompt_type == "unified":
        if not prompt:
            raise ValueError("prompt is required for unified type")
        entry["prompt"] = prompt

    elif prompt_type == "per-type":
        if prompt_dir:
            # Load prompts from directory
            prompts = {}
            prompt_dir = Path(prompt_dir)

            for video_type, filename in VIDEO_TYPE_FILES.items():
                file_path = prompt_dir / filename
                if file_path.exists():
                    with open(file_path, "r", encoding="utf-8") as f:
                        prompts[video_type] = f.read().strip()
                else:
                    print(f"[WARN] Missing prompt file: {file_path}")

            if not prompts:
                raise ValueError(f"No prompt files found in {prompt_dir}")

        if not prompts:
            raise ValueError("prompts dict or prompt_dir is required for per-type")

        entry["prompts"] = prompts

    else:
        raise ValueError(f"Invalid prompt_type: {prompt_type}")

    # Add to registry
    registry = _load_registry()
    registry.setdefault("prompt_versions", []).append(entry)
    _save_registry(registry)

    return entry


def set_status(prompt_id: str, status: str) -> bool:
    """
    Update the status of a prompt version.

    Args:
        prompt_id: The prompt ID to update
        status: New status (deprecated, baseline, production, draft)

    Returns:
        True if updated, False if not found
    """
    valid_statuses = ["deprecated", "baseline", "production", "draft"]
    if status not in valid_statuses:
        raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")

    registry = _load_registry()
    for entry in registry.get("prompt_versions", []):
        if entry.get("id") == prompt_id:
            entry["status"] = status
            _save_registry(registry)
            return True

    return False


def delete_prompt(prompt_id: str) -> bool:
    """
    Delete a prompt version from the registry.

    Args:
        prompt_id: The prompt ID to delete

    Returns:
        True if deleted, False if not found
    """
    registry = _load_registry()
    versions = registry.get("prompt_versions", [])

    for i, entry in enumerate(versions):
        if entry.get("id") == prompt_id:
            versions.pop(i)
            _save_registry(registry)
            return True

    return False
