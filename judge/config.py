"""
Judge Configuration

Handles model selection (Bedrock/OpenAI) and provides judge client classes
with a shared evaluate(system_prompt, user_prompt) interface.
"""

import json
import os
import re
from abc import ABC, abstractmethod
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# Judge provider: "bedrock" or "openai"
JUDGE_PROVIDER = os.getenv("JUDGE_PROVIDER", "openai")

# Model IDs
JUDGE_MODEL_BEDROCK = os.getenv("JUDGE_MODEL_BEDROCK", "moonshot.kimi-k2-thinking")
JUDGE_MODEL_OPENAI = os.getenv("JUDGE_MODEL_OPENAI", "gpt-4o")

# Script Quality dimensions (LLM-judged) - equal weight, simple average
SCRIPT_QUALITY_DIMENSIONS = [
    "hook_quality",
    "tone_match",
    "structural_flow",
    "content_richness",
    "completeness",
]

# System Metrics (deterministic scorers) - reported separately
SYSTEM_METRIC_DIMENSIONS = [
    "timing_accuracy",
    "template_compatibility",
]

# Legacy weighted composite (for backward compatibility)
# timing_accuracy and template_compatibility are now system metrics, not part of script quality
WEIGHTS = {
    "timing_accuracy": 0.20,
    "template_compatibility": 0.20,
    "hook_quality": 0.10,
    "tone_match": 0.15,
    "structural_flow": 0.15,
    "content_richness": 0.10,
    "completeness": 0.10,
}


def strip_json_fences(text: str) -> str:
    """
    Strip markdown JSON fences from text if present.

    Handles:
    - ```json ... ```
    - ``` ... ```
    """
    # Pattern to match ```json or ``` at start and ``` at end
    pattern = r'^```(?:json)?\s*\n?(.*?)\n?```$'
    match = re.match(pattern, text.strip(), re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def parse_judge_response(text: str) -> dict:
    """
    Parse JSON response from judge, handling markdown fences.

    Args:
        text: Raw response text from the judge

    Returns:
        Parsed JSON as dict

    Raises:
        json.JSONDecodeError: If parsing fails
    """
    cleaned = strip_json_fences(text)
    return json.loads(cleaned)


class BaseJudge(ABC):
    """Abstract base class for judge implementations."""

    @abstractmethod
    def evaluate(self, system_prompt: str, user_prompt: str) -> dict:
        """
        Evaluate a script using the judge model.

        Args:
            system_prompt: The judge system prompt
            user_prompt: The user prompt with script and rubric

        Returns:
            Parsed JSON response as dict
        """
        pass


class BedrockJudge(BaseJudge):
    """Judge using Kimi K2 Thinking via Amazon Bedrock."""

    def __init__(self, client, model_id: str):
        self.client = client
        self.model_id = model_id

    def evaluate(self, system_prompt: str, user_prompt: str) -> dict:
        """Evaluate using Bedrock converse API."""
        response = self.client.converse(
            modelId=self.model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": user_prompt}]
                }
            ],
            system=[{"text": system_prompt}],
            inferenceConfig={
                "temperature": 0.3,
                "maxTokens": 4096,
            }
        )

        # Extract text from response - handle multiple content block types
        output_message = response.get("output", {}).get("message", {})
        content_blocks = output_message.get("content", [])

        # Thinking models (like Kimi K2) may return multiple content blocks:
        # - reasoningContent: the thinking/reasoning process
        # - text: the final answer
        # We need to find the text block with the actual JSON response
        text_content = None

        for block in content_blocks:
            # Standard text block
            if "text" in block:
                text_content = block["text"]
            # Some models use different keys
            elif "value" in block:
                text_content = block["value"]

        # If we found text content, try to parse it
        if text_content:
            return parse_judge_response(text_content)

        # Debug: include response structure in error
        import json as _json
        response_preview = _json.dumps(response, default=str)[:500]
        raise ValueError(f"No text content in Bedrock response. Structure: {response_preview}")


class OpenAIJudge(BaseJudge):
    """Judge using OpenAI models."""

    def __init__(self, client, model_id: str):
        self.client = client
        self.model_id = model_id

    def evaluate(self, system_prompt: str, user_prompt: str) -> dict:
        """Evaluate using OpenAI chat completions API."""
        response = self.client.chat.completions.create(
            model=self.model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        content = response.choices[0].message.content
        return parse_judge_response(content)


def get_judge_client() -> BaseJudge:
    """
    Get the configured judge client based on environment variables.

    Returns:
        BedrockJudge or OpenAIJudge instance

    Raises:
        ValueError: If JUDGE_PROVIDER is invalid or credentials missing
    """
    if JUDGE_PROVIDER == "bedrock":
        import boto3

        aws_profile = os.getenv("AWS_PROFILE")
        aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

        session = boto3.Session(profile_name=aws_profile)
        client = session.client("bedrock-runtime", region_name=aws_region)

        return BedrockJudge(client, JUDGE_MODEL_BEDROCK)

    elif JUDGE_PROVIDER == "openai":
        from openai import OpenAI

        api_key = os.getenv("OPEN_API")
        if not api_key:
            raise ValueError("OPEN_API environment variable not set")

        client = OpenAI(api_key=api_key)
        return OpenAIJudge(client, JUDGE_MODEL_OPENAI)

    else:
        raise ValueError(f"Unknown JUDGE_PROVIDER: {JUDGE_PROVIDER}")
