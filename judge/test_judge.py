"""
Judge Sanity Check Script

Tests the full judge pipeline on 3 sample scripts:
1. A short tutorial (good timing) - expected decent scores
2. A long explainer (good timing) - tests longer script handling
3. A medium marketing script - tests different video type

Run with: python -m judge.test_judge
"""

import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from judge.evaluate import evaluate_script, judge_result_to_json, judge_result_to_dict


# Sample records from parsed_records.json
# These are embedded directly so the test can run standalone

SAMPLE_SCRIPTS = [
    # Script 1: Short tutorial - Kaspa (131 words, 56.1s estimated, target 60s)
    {
        "id": "000050d0-cfac-4303-b27b-6b13de4d8cee",
        "valid": True,
        "english": True,
        "video_type": "Tutorial",
        "subject": "Kaspa",
        "duration_range": "1min",
        "duration_min_sec": 60,
        "duration_max_sec": 60,
        "duration_midpoint_sec": 60,
        "platform": "YouTube",
        "script": """Mastering Kaspa: A Quick Guide to Fast Transactions

Are you struggling to understand Kaspa? Many find it complex. This tutorial will clarify how to use Kaspa effectively. Our goal is to get you familiar with fast transactions on Kaspa.

First, visit the official Kaspa website. This is your starting point. Next, download the Kaspa wallet. It'll help you manage transactions easily.

Once installed, create an account. Make sure to keep your credentials safe. After this, add funds to your wallet. You can do this through various exchanges.

Finally, practice sending and receiving transactions. Observe how quickly they process. This will give you hands-on experience.

In summary, we covered how to access and use Kaspa. You learned about downloading, creating an account, and transactions. Now, apply this knowledge to navigate Kaspa smoothly!""",
        "word_count": 131,
        "char_count": 849,
        "estimated_time_sec": 56.1
    },

    # Script 2: Marketing script with multiple benefits - GoRaven (138 words, 59.1s estimated, target 60-300s)
    {
        "id": "000054e2-257c-4770-90f4-c177b5f04339",
        "valid": True,
        "english": True,
        "video_type": "Marketing",
        "subject": "GoRaven - B2B AI-powered SaaS company",
        "duration_range": "1min - 5min",
        "duration_min_sec": 60,
        "duration_max_sec": 300,
        "duration_midpoint_sec": 180,
        "platform": "YouTube",
        "script": """GoRaven: Creating Clarity, Calm, and Freedom for Small Business Owners

Imagine a world where your business serves your life.

At GoRaven Limited, we're more than just software.

We empower small business owners to save time and make money.

Picture this: success and freedom for every small business in the UK.

Our mission is simple: Prove results, Sell values, Relate authentically.

Founded on values of kindness, integrity, humility, and authenticity.

We believe every person and business has inherent value.

It's time to embrace a new way of working.

You can be less busy and still thrive.

We'll show you how to do what matters, efficiently.

Freedom isn't about doing more; it's about doing it right.

Join us on this journey to clarity, calm, and freedom.

Let's make your business work for you.

Visit GoRaven today and start your transformation.""",
        "word_count": 138,
        "char_count": 872,
        "estimated_time_sec": 59.1
    },

    # Script 3: Explainer about cultural identity (187 words, 80.1s estimated, target 60-300s)
    {
        "id": "00000d73-8c38-4ba3-b5ae-14b130d7f411",
        "valid": True,
        "english": True,
        "video_type": "Explainer",
        "subject": "The Cultural Glitch: Mempertahankan Jati Diri di Arus Global",
        "duration_range": "1min - 5min",
        "duration_min_sec": 60,
        "duration_max_sec": 300,
        "duration_midpoint_sec": 180,
        "platform": "Instagram Reels",
        "script": """The Cultural Glitch: Mempertahankan Jati Diri di Arus Global

What defines us in a fast-changing world? Explore the cultural glitch today!

Globalization connects us, but it risks erasing unique identities. How do we keep our traditions alive?

First, understand cultural identity. It consists of values, beliefs, and customs. This is who we are at our core.

Next, notice the impact of global culture. Social media influences every corner of life. Trends spread rapidly, often replacing local traditions.

Now, let's keep our traditions alive. One way is through storytelling. Share stories with younger generations. Teach them about your culture.

Another method is through art. Music, dance, and visual arts reflect our identity. Encourage creative expression that showcases your culture.

Engagement is key. Join local events and celebrate your heritage. Help others appreciate your background while learning from theirs.

Remember, embracing global culture doesn't mean losing your identity. It's about blending the old with the new.

In summary, understanding your cultural identity is vital. Share stories and art. Engage with your community.

Stay rooted while exploring the world around you. Want to learn more? Follow for more cultural insights!""",
        "word_count": 187,
        "char_count": 1261,
        "estimated_time_sec": 80.1
    },
]


def print_result_summary(result_dict: dict, script_name: str):
    """Print a formatted summary of judge results."""
    print("\n" + "=" * 70)
    print(f"RESULTS: {script_name}")
    print("=" * 70)

    metadata = result_dict["metadata"]
    print(f"\nMetadata:")
    print(f"  Video Type: {metadata['video_type']}")
    print(f"  Subject: {metadata['subject'][:50]}..." if len(str(metadata['subject'])) > 50 else f"  Subject: {metadata['subject']}")
    print(f"  Duration Range: {metadata['duration_range']}")
    print(f"  Platform: {metadata['platform']}")

    print(f"\nComposite Score: {result_dict['composite_score']:.2f}")

    print("\nDimension Scores:")
    scores = result_dict["scores"]

    # Deterministic scores
    timing = scores.get("timing_accuracy", {})
    print(f"  Timing Accuracy:        {timing.get('score', 'ERR'):>2} (est: {timing.get('estimated_duration_sec', 'N/A')}s, "
          f"target: {timing.get('target_min_sec')}-{timing.get('target_max_sec')}s)")

    template = scores.get("template_compatibility", {})
    if "error" in template:
        print(f"  Template Compatibility: ERR - {template.get('error', 'Unknown error')[:50]}...")
    else:
        print(f"  Template Compatibility: {template.get('score', 'ERR'):>2} ({template.get('category_count', 0)} categories)")

    # LLM scores
    for dim in ["hook_quality", "tone_match", "structural_flow", "content_richness", "completeness"]:
        dim_data = scores.get(dim, {})
        dim_name = dim.replace("_", " ").title()
        if "error" in dim_data:
            print(f"  {dim_name:22} ERR - {dim_data.get('error', 'Unknown')[:40]}...")
        else:
            score = dim_data.get("score", "N/A")
            justification = dim_data.get("justification", "")[:60]
            print(f"  {dim_name:22} {score:>2} - {justification}...")

    # Improvements
    improvements = result_dict.get("all_improvements", [])
    if improvements:
        print(f"\nTop Improvements ({len(improvements)} total):")
        for imp in improvements[:3]:
            print(f"  - {imp[:70]}..." if len(imp) > 70 else f"  - {imp}")

    print()


def main():
    print("=" * 70)
    print("JUDGE SANITY CHECK")
    print("=" * 70)
    print("\nThis script tests the judge pipeline on 3 sample scripts.")
    print("It verifies JSON parsing, score ranges, and CoT reasoning.\n")

    results = []

    for i, record in enumerate(SAMPLE_SCRIPTS, 1):
        script_name = f"Script {i}: {record['video_type']} - {record['subject'][:30]}..."
        print(f"\n[{i}/3] Evaluating {script_name}")
        print("-" * 50)

        try:
            result = evaluate_script(record, prompt_version="test-v1")
            result_dict = judge_result_to_dict(result)
            results.append(result_dict)

            print_result_summary(result_dict, script_name)

            # Validation checks
            print("Validation:")

            # Check score is in valid range
            composite = result_dict["composite_score"]
            if 1.0 <= composite <= 5.0:
                print(f"  [OK] Composite score {composite:.2f} is in valid range [1-5]")
            else:
                print(f"  [WARN] Composite score {composite:.2f} outside valid range [1-5]")

            # Check all dimensions have scores
            missing_scores = []
            for dim in ["timing_accuracy", "template_compatibility", "hook_quality",
                        "tone_match", "structural_flow", "content_richness", "completeness"]:
                dim_data = result_dict["scores"].get(dim, {})
                if "error" in dim_data or dim_data.get("score") is None:
                    missing_scores.append(dim)

            if not missing_scores:
                print("  [OK] All 7 dimensions have scores")
            else:
                print(f"  [WARN] Missing/error scores for: {', '.join(missing_scores)}")

            # Check LLM dimensions have CoT reasoning
            for dim in ["hook_quality", "tone_match", "structural_flow", "content_richness", "completeness"]:
                dim_data = result_dict["scores"].get(dim, {})
                cot = dim_data.get("chain_of_thought", "")
                if cot and len(cot) > 100:
                    print(f"  [OK] {dim.replace('_', ' ').title()} has CoT reasoning ({len(cot)} chars)")
                elif "error" in dim_data:
                    print(f"  [SKIP] {dim.replace('_', ' ').title()} - API error")
                else:
                    print(f"  [WARN] {dim.replace('_', ' ').title()} has short/missing CoT")

        except Exception as e:
            print(f"  [ERROR] Evaluation failed: {e}")
            import traceback
            traceback.print_exc()

    # Save results to file
    output_path = PROJECT_ROOT / "data" / "judge_test_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n[SAVED] Results written to: {output_path}")

    # Final summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    successful = len([r for r in results if r.get("composite_score")])
    print(f"Scripts evaluated: {successful}/{len(SAMPLE_SCRIPTS)}")

    if successful > 0:
        scores = [r["composite_score"] for r in results if r.get("composite_score")]
        print(f"Composite score range: {min(scores):.2f} - {max(scores):.2f}")
        print(f"Composite score mean: {sum(scores) / len(scores):.2f}")

    print("\n[DONE] Judge sanity check complete.")


if __name__ == "__main__":
    main()
