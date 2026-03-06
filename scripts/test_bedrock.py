"""
Sanity check for Kimi K2 Thinking via Amazon Bedrock.

Run with: python scripts/test_bedrock.py
"""

import os
import json
from dotenv import load_dotenv

load_dotenv()


def test_bedrock_kimi():
    """Test Kimi K2 Thinking model through Bedrock."""
    import boto3

    # Get AWS config from environment
    aws_profile = os.getenv("AWS_PROFILE")
    aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    model_id = os.getenv("JUDGE_MODEL_BEDROCK", "moonshot.kimi-k2-thinking")

    print("=" * 60)
    print("Bedrock Kimi K2 Thinking - Sanity Check")
    print("=" * 60)
    print(f"AWS Profile: {aws_profile}")
    print(f"AWS Region:  {aws_region}")
    print(f"Model ID:    {model_id}")
    print("=" * 60)

    # Create Bedrock client
    print("\n[1] Creating Bedrock client...")
    try:
        session = boto3.Session(profile_name=aws_profile)
        client = session.client("bedrock-runtime", region_name=aws_region)
        print("    OK - Client created")
    except Exception as e:
        print(f"    FAILED - {e}")
        return False

    # Test message
    system_prompt = "You are a helpful assistant. Respond briefly."
    user_prompt = "Say 'Hello from Kimi K2!' and nothing else."

    print(f"\n[2] Sending test request to {model_id}...")
    print(f"    System: {system_prompt}")
    print(f"    User:   {user_prompt}")

    try:
        response = client.converse(
            modelId=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": user_prompt}]
                }
            ],
            system=[{"text": system_prompt}],
            inferenceConfig={
                "temperature": 0.3,
                "maxTokens": 100,
            }
        )

        # Extract response
        output_message = response.get("output", {}).get("message", {})
        content = output_message.get("content", [])

        if content and "text" in content[0]:
            response_text = content[0]["text"]
            print(f"\n[3] Response received:")
            print(f"    {response_text}")
        else:
            print(f"\n[3] Unexpected response format:")
            print(f"    {json.dumps(response, indent=2)}")

        # Print usage stats if available
        usage = response.get("usage", {})
        if usage:
            print(f"\n[4] Usage:")
            print(f"    Input tokens:  {usage.get('inputTokens', 'N/A')}")
            print(f"    Output tokens: {usage.get('outputTokens', 'N/A')}")

        print("\n" + "=" * 60)
        print("SUCCESS - Bedrock Kimi K2 Thinking is working!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n    FAILED - {e}")
        print("\n" + "=" * 60)
        print("FAILED - Check your AWS credentials and model access")
        print("=" * 60)
        return False


if __name__ == "__main__":
    test_bedrock_kimi()
