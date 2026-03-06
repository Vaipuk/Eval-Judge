"""
Batch Evaluation Runner

Runs evaluation for a prompt version against the full test suite.
Handles script generation, judging, and result persistence.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

from .prompt_registry import get_prompt_entry, get_prompt, VIDEO_TYPES
from judge.evaluate import evaluate_script, judge_result_to_dict, JudgeResult
from judge.config import get_judge_client, JUDGE_PROVIDER, JUDGE_MODEL_BEDROCK, JUDGE_MODEL_OPENAI
from scorers.timing import count_words, estimate_duration_sec

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent
TEST_SUITE_PATH = PROJECT_ROOT / "data" / "test_suite.json"
PARSED_RECORDS_PATH = PROJECT_ROOT / "data" / "parsed_records.json"
RUNS_DIR = PROJECT_ROOT / "data" / "runs"


# Cost estimates per 1M tokens (input/output)
COST_ESTIMATES = {
    # Generation models
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    # Judge models
    "moonshot.kimi-k2-thinking": {"input": 0.60, "output": 2.00},
    "gpt-5.2": {"input": 5.00, "output": 15.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}

# Estimated tokens per call
ESTIMATED_TOKENS = {
    "generation": {"input": 1500, "output": 800},
    "template_classification": {"input": 2000, "output": 500},
    "judge_dimension": {"input": 3000, "output": 1000},
}


def _get_openai_client() -> OpenAI:
    """Create OpenAI client from environment."""
    api_key = os.getenv("OPEN_API")
    if not api_key:
        raise ValueError("OPEN_API environment variable not set")
    return OpenAI(api_key=api_key)


def _build_user_message(test_input: dict) -> str:
    """
    Build the user message for script generation.

    Format matches the production Agenta template.
    """
    subject = test_input.get("subject", "")
    duration_range = test_input.get("duration_range") or "1min"
    platform = test_input.get("platform") or "General"

    return (
        f"text: {subject}\n"
        f"tone: match the subject theme\n"
        f"duration: {duration_range}\n"
        f"platform: {platform}\n"
        f"additionalInformation: "
    )


def _generate_script_with_retry(
    client: OpenAI,
    system_prompt: str,
    user_message: str,
    model: str,
    max_retries: int = 2,
) -> tuple[str, Optional[str]]:
    """
    Generate a script with retry on failure.

    Returns:
        (script_text, error_message)
        - On success: (script, None)
        - On failure: ("", error_message)
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.7,
                max_tokens=4000,
            )
            return response.choices[0].message.content.strip(), None

        except Exception as e:
            last_error = str(e)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue

    return "", f"Generation failed after {max_retries} attempts: {last_error}"


def estimate_run_cost(
    num_inputs: int,
    generation_model: str,
    judge_model: str,
    use_historical: bool = False,
) -> dict:
    """
    Estimate the cost of an evaluation run.

    Each input requires:
    - 1 generation call (skipped if use_historical=True)
    - 1 template classification call (gpt-4o-mini)
    - 5 judge dimension calls

    Args:
        num_inputs: Number of test inputs to process
        generation_model: Model used for generation
        judge_model: Model used for judging
        use_historical: If True, skip generation cost (using pre-generated scripts)

    Returns dict with per-component costs and total.
    """
    gen_costs = COST_ESTIMATES.get(generation_model, COST_ESTIMATES["gpt-4o-mini"])
    template_costs = COST_ESTIMATES["gpt-4o-mini"]
    judge_costs = COST_ESTIMATES.get(judge_model, COST_ESTIMATES["gpt-4o"])

    # Generation cost (zero if using historical scripts)
    if use_historical:
        generation_total = 0.0
    else:
        gen_input_cost = (ESTIMATED_TOKENS["generation"]["input"] / 1_000_000) * gen_costs["input"] * num_inputs
        gen_output_cost = (ESTIMATED_TOKENS["generation"]["output"] / 1_000_000) * gen_costs["output"] * num_inputs
        generation_total = gen_input_cost + gen_output_cost

    # Template classification cost
    tmpl_input_cost = (ESTIMATED_TOKENS["template_classification"]["input"] / 1_000_000) * template_costs["input"] * num_inputs
    tmpl_output_cost = (ESTIMATED_TOKENS["template_classification"]["output"] / 1_000_000) * template_costs["output"] * num_inputs
    template_total = tmpl_input_cost + tmpl_output_cost

    # Judge cost (5 dimensions per input)
    judge_input_cost = (ESTIMATED_TOKENS["judge_dimension"]["input"] / 1_000_000) * judge_costs["input"] * num_inputs * 5
    judge_output_cost = (ESTIMATED_TOKENS["judge_dimension"]["output"] / 1_000_000) * judge_costs["output"] * num_inputs * 5
    judge_total = judge_input_cost + judge_output_cost

    return {
        "generation": round(generation_total, 2),
        "template_classification": round(template_total, 2),
        "judge": round(judge_total, 2),
        "total": round(generation_total + template_total + judge_total, 2),
        "generation_model": generation_model,
        "judge_model": judge_model,
        "use_historical": use_historical,
    }


def _load_test_suite() -> list[dict]:
    """Load test suite from JSON file."""
    with open(TEST_SUITE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_parsed_records() -> dict[str, dict]:
    """
    Load parsed records and build a lookup by ID.

    Returns:
        Dict mapping record ID to full record (including script)
    """
    if not PARSED_RECORDS_PATH.exists():
        return {}

    with open(PARSED_RECORDS_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)

    return {r.get("id"): r for r in records if r.get("id")}


def _generate_run_id(prompt_version: str) -> str:
    """Generate a unique run ID."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"eval-{prompt_version}-{timestamp}"


def _save_run_result(run_id: str, result: dict) -> Path:
    """Save run result to JSON file."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RUNS_DIR / f"{run_id}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    return output_path


def _save_intermediate(run_id: str, result: dict) -> None:
    """Save intermediate results (for crash recovery)."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RUNS_DIR / f"{run_id}_partial.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)


def _remove_intermediate(run_id: str) -> None:
    """Remove intermediate file after successful completion."""
    partial_path = RUNS_DIR / f"{run_id}_partial.json"
    if partial_path.exists():
        partial_path.unlink()


def run_evaluation(
    prompt_version: str,
    test_suite: Optional[list[dict]] = None,
    skip_confirmation: bool = False,
    save_intermediate: bool = True,
    max_inputs: Optional[int] = None,
) -> dict:
    """
    Run a full evaluation for a prompt version.

    Args:
        prompt_version: ID of the prompt version to test
        test_suite: Optional custom test suite (defaults to data/test_suite.json)
        skip_confirmation: If True, don't prompt for cost confirmation
        save_intermediate: If True, save results after each evaluation
        max_inputs: Optional limit on number of inputs to process (for testing)

    Returns:
        Complete run result dict with metadata, results, and statistics
    """
    # Load prompt entry
    prompt_entry = get_prompt_entry(prompt_version)
    if not prompt_entry:
        raise ValueError(f"Prompt version '{prompt_version}' not found in registry")

    prompt_type = prompt_entry.get("type", "unified")
    generation_model = prompt_entry.get("model", "gpt-4o-mini")
    use_historical = prompt_entry.get("use_historical", False)

    # Determine judge model
    if JUDGE_PROVIDER == "bedrock":
        judge_model = JUDGE_MODEL_BEDROCK
    else:
        judge_model = JUDGE_MODEL_OPENAI

    # Load test suite
    if test_suite is None:
        test_suite = _load_test_suite()

    if max_inputs:
        test_suite = test_suite[:max_inputs]

    num_inputs = len(test_suite)

    # Load parsed records for historical mode
    parsed_records = {}
    if use_historical:
        parsed_records = _load_parsed_records()
        if not parsed_records:
            raise ValueError("use_historical=True but parsed_records.json not found or empty")

    # Estimate cost
    cost_estimate = estimate_run_cost(num_inputs, generation_model, judge_model, use_historical)

    print("\n" + "=" * 60)
    print("EVALUATION RUN")
    print("=" * 60)
    print(f"Prompt Version: {prompt_version}")
    print(f"Prompt Type: {prompt_type}")

    if use_historical:
        print("")
        print("[HISTORICAL MODE] Using pre-generated scripts from parsed_records.json")
        print("Generation cost: $0.00")
        print("Only judging costs apply.")
        print("")
    else:
        print(f"Generation Model: {generation_model}")

    print(f"Judge Model: {judge_model} ({JUDGE_PROVIDER})")
    print(f"Test Inputs: {num_inputs}")
    print(f"\nEstimated Cost:")
    print(f"  Generation:     ${cost_estimate['generation']:.2f}" + (" (historical)" if use_historical else ""))
    print(f"  Template Class: ${cost_estimate['template_classification']:.2f}")
    print(f"  Judge:          ${cost_estimate['judge']:.2f}")
    print(f"  -------------------")
    print(f"  TOTAL:          ${cost_estimate['total']:.2f}")
    print("=" * 60)

    if not skip_confirmation:
        confirm = input("\nProceed with evaluation? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Evaluation cancelled.")
            return {}

    # Initialize clients
    openai_client = _get_openai_client()
    judge_client = get_judge_client()

    # Generate run ID
    run_id = _generate_run_id(prompt_version)
    print(f"\nRun ID: {run_id}")
    print("-" * 60)

    # Initialize result structure
    result = {
        "run_id": run_id,
        "prompt_version": prompt_version,
        "prompt_type": prompt_type,
        "generation_model": generation_model if not use_historical else "historical",
        "use_historical": use_historical,
        "judge_model": judge_model,
        "judge_provider": JUDGE_PROVIDER,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "test_suite_size": num_inputs,
        "cost_estimate": cost_estimate,
        "results": [],
        "errors": [],
        "statistics": {},
    }

    # Process each test input
    start_time = time.time()

    for i, test_input in enumerate(test_suite):
        input_id = test_input.get("id", f"unknown-{i}")
        video_type = test_input.get("video_type", "Explainer")
        subject = test_input.get("subject", "Unknown")

        # Truncate subject for display
        subject_display = subject[:50] + "..." if len(subject) > 50 else subject
        print(f"[{i+1}/{num_inputs}] Evaluating {video_type} script: \"{subject_display}\"")

        # Get script: historical or generated
        if use_historical:
            # Look up historical script from parsed_records
            historical_record = parsed_records.get(input_id)
            if not historical_record:
                error_msg = f"No historical record found for ID '{input_id}' in parsed_records.json"
                print(f"  [SKIP] {error_msg}")
                result["errors"].append({
                    "input_id": input_id,
                    "error": error_msg,
                })
                continue

            script = historical_record.get("script", "")
            if not script:
                error_msg = f"Historical record '{input_id}' has no script"
                print(f"  [SKIP] {error_msg}")
                result["errors"].append({
                    "input_id": input_id,
                    "error": error_msg,
                })
                continue

            # Use word_count from historical record if available
            word_count = historical_record.get("word_count") or count_words(script)
            estimated_time = historical_record.get("estimated_time_sec") or estimate_duration_sec(word_count)

        else:
            # Generate script live
            # Get the appropriate system prompt
            if prompt_type == "unified":
                system_prompt = get_prompt(prompt_version)
            else:  # per-type
                system_prompt = get_prompt(prompt_version, video_type)
                if not system_prompt:
                    error_msg = f"No prompt found for video type '{video_type}' in prompt version '{prompt_version}'"
                    print(f"  [SKIP] {error_msg}")
                    result["errors"].append({
                        "input_id": input_id,
                        "error": error_msg,
                    })
                    continue

            if not system_prompt:
                error_msg = f"Could not load prompt for version '{prompt_version}'"
                print(f"  [ERROR] {error_msg}")
                result["errors"].append({
                    "input_id": input_id,
                    "error": error_msg,
                })
                continue

            # Build user message and generate script
            user_message = _build_user_message(test_input)
            script, gen_error = _generate_script_with_retry(
                openai_client, system_prompt, user_message, generation_model
            )

            if gen_error:
                print(f"  [ERROR] Generation failed: {gen_error}")
                result["errors"].append({
                    "input_id": input_id,
                    "error": gen_error,
                })
                continue

            word_count = count_words(script)
            estimated_time = estimate_duration_sec(word_count)

        # Build full record for judge
        record = {
            "id": input_id,
            "video_type": video_type,
            "subject": subject,
            "duration_range": test_input.get("duration_range"),
            "duration_min_sec": test_input.get("duration_min_sec"),
            "duration_max_sec": test_input.get("duration_max_sec"),
            "platform": test_input.get("platform"),
            "script": script,
            "word_count": word_count,
            "estimated_time_sec": estimated_time,
        }

        # Run evaluation
        try:
            judge_result = evaluate_script(
                record,
                prompt_version=prompt_version,
                judge=judge_client,
                openai_client=openai_client,
            )

            # Convert to dict and add script info
            result_dict = judge_result_to_dict(judge_result)
            result_dict["generated_script"] = script
            result_dict["word_count"] = word_count
            result_dict["estimated_time_sec"] = estimated_time
            result_dict["script_source"] = "historical" if use_historical else "generated"
            result_dict["test_input"] = {
                "id": input_id,
                "video_type": video_type,
                "subject": subject,
                "duration_range": test_input.get("duration_range"),
                "platform": test_input.get("platform"),
            }

            result["results"].append(result_dict)

            # Print score summary
            script_quality = judge_result.script_quality_score
            timing = judge_result.scores.get("timing_accuracy", {}).get("score", "?")
            template = judge_result.scores.get("template_compatibility", {}).get("score", "?")
            print(f"  [OK] Script Quality: {script_quality:.2f} | Timing: {timing} | Template: {template}")

        except Exception as e:
            error_msg = f"Evaluation failed: {str(e)}"
            print(f"  [ERROR] {error_msg}")
            result["errors"].append({
                "input_id": input_id,
                "error": error_msg,
            })

        # Save intermediate results
        if save_intermediate and (i + 1) % 5 == 0:
            _save_intermediate(run_id, result)

    # Calculate run duration
    elapsed_time = time.time() - start_time
    result["duration_seconds"] = round(elapsed_time, 1)

    # Calculate basic statistics
    if result["results"]:
        composites = [r["composite_score"] for r in result["results"]]
        script_qualities = [r["script_quality_score"] for r in result["results"]]
        result["statistics"] = {
            "total_evaluated": len(result["results"]),
            "total_errors": len(result["errors"]),
            "composite_mean": round(sum(composites) / len(composites), 2),
            "composite_min": round(min(composites), 2),
            "composite_max": round(max(composites), 2),
            "script_quality_mean": round(sum(script_qualities) / len(script_qualities), 2),
            "script_quality_min": round(min(script_qualities), 2),
            "script_quality_max": round(max(script_qualities), 2),
        }

    # Save final result
    output_path = _save_run_result(run_id, result)
    _remove_intermediate(run_id)

    # Print summary
    print("\n" + "=" * 60)
    print("EVALUATION COMPLETE")
    print("=" * 60)
    print(f"Run ID: {run_id}")
    print(f"Duration: {elapsed_time:.1f}s")
    print(f"Evaluated: {len(result['results'])}/{num_inputs}")
    print(f"Errors: {len(result['errors'])}")
    if use_historical:
        print(f"Mode: Historical scripts")

    if result["statistics"]:
        print(f"\nScript Quality:")
        print(f"  Mean: {result['statistics']['script_quality_mean']:.2f}")
        print(f"  Min:  {result['statistics']['script_quality_min']:.2f}")
        print(f"  Max:  {result['statistics']['script_quality_max']:.2f}")

    print(f"\nResults saved to: {output_path}")
    print("=" * 60)

    return result
