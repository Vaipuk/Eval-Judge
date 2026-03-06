# Pictory Script Evaluation Judge

A comprehensive LLM-based evaluation pipeline for comparing video script generation prompts. This system generates scripts using different prompt versions, scores them across multiple dimensions, and provides statistical analysis to detect improvements and regressions.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Setup](#setup)
4. [Configuration](#configuration)
5. [Prompt Management](#prompt-management)
6. [Running Evaluations](#running-evaluations)
7. [Comparing Runs](#comparing-runs)
8. [Understanding Results](#understanding-results)
9. [File Structure](#file-structure)
10. [Scoring Dimensions](#scoring-dimensions)
11. [Models Used](#models-used)
12. [Troubleshooting](#troubleshooting)

---

## Overview

The Evaluation Judge system helps answer: **"Did my prompt changes actually improve script quality?"**

### Key Features

- **A/B Testing for Prompts**: Compare legacy per-type prompts vs unified prompts
- **Multi-Dimensional Scoring**: 7 quality dimensions evaluated by an LLM judge
- **Statistical Significance**: Wilcoxon signed-rank test to detect real improvements
- **Feedback Clustering**: LLM-powered grouping of common issues
- **Cost Estimation**: Know the API cost before running expensive evaluations
- **Crash Recovery**: Intermediate saves let you resume failed runs

### Workflow

```
Test Suite (JSON) → Script Generation → LLM Scoring → Aggregation → Comparison Report
                         ↓                  ↓
                    [Old Prompt]        [Judge Model]
                    [New Prompt]        (Kimi K2 / GPT-4o)
```

---

## Architecture

### Components

| Component | File | Purpose |
|-----------|------|---------|
| Prompt Registry | `evaluator/prompt_registry.py` | Manage prompt versions (unified vs per-type) |
| Evaluation Runner | `evaluator/run.py` | Generate scripts and run scorers |
| Score Aggregator | `evaluator/aggregate.py` | Compute statistics and cluster feedback |
| Run Comparator | `evaluator/compare.py` | Statistical comparison between runs |
| Report Generator | `evaluator/report.py` | Markdown reports |
| CLI | `evaluator/cli.py` | Command-line interface |

### Two Prompt Architectures

1. **Per-Type (Legacy)**: Separate prompts for each video category
   - `prompts/legacy/explainer.txt`
   - `prompts/legacy/marketing.txt`
   - `prompts/legacy/tutorial.txt`
   - `prompts/legacy/internal_comms.txt`
   - `prompts/legacy/product_intro.txt`

2. **Unified (New)**: Single prompt handles all video categories
   - `prompts/unified/unified_v1.txt`

### Historical Mode

Prompts can use pre-existing scripts from `parsed_records.json` instead of generating new ones. This is useful for evaluating legacy prompts against their actual production output.

To enable historical mode, set `use_historical: true` in the prompt registry:

```json
{
  "id": "legacy-v1.0",
  "type": "per-type",
  "model": "gpt-4o-mini",
  "use_historical": true,
  "prompts": { ... }
}
```

When historical mode is enabled:
- Generation is skipped (scripts are loaded from `parsed_records.json`)
- Generation cost is $0.00
- Only judging costs apply
- Scripts are matched by ID from the test suite

CLI output shows:
```
[HISTORICAL MODE] Using pre-generated scripts from parsed_records.json
Generation cost: $0.00
Only judging costs apply.
```

---

## Setup

### 1. Install Dependencies

```bash
pip install boto3 python-dotenv scipy openai
```

### 2. Configure Environment

Copy the example environment file:

```bash
cp .env-example .env
```

Edit `.env` with your credentials:

```env
# AWS Configuration (for Bedrock)
AWS_PROFILE=your-aws-profile
AWS_DEFAULT_REGION=us-east-2

# OpenAI Configuration
OPEN_API=""key-here""

# Judge Configuration
JUDGE_PROVIDER=bedrock          # or "openai"
JUDGE_MODEL_BEDROCK=moonshot.kimi-k2-thinking
JUDGE_MODEL_OPENAI=gpt-4o
```

### 3. Verify Bedrock Access

Run the sanity check script:

```bash
python scripts/test_bedrock.py
```

Expected output:
```
============================================================
Bedrock Kimi K2 Thinking - Sanity Check
============================================================
AWS Profile: your-profile
AWS Region:  us-east-2
Model ID:    moonshot.kimi-k2-thinking
============================================================

[1] Creating Bedrock client...
    OK - Client created

[2] Sending test request...
[3] Response received:
    Hello from Kimi K2!

============================================================
SUCCESS - Bedrock Kimi K2 Thinking is working!
============================================================
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_PROFILE` | AWS credentials profile name | Required for Bedrock |
| `AWS_DEFAULT_REGION` | AWS region | `us-east-1` |
| `JUDGE_PROVIDER` | `bedrock` or `openai` | `bedrock` |
| `JUDGE_MODEL_BEDROCK` | Bedrock model ID | `moonshot.kimi-k2-thinking` |
| `JUDGE_MODEL_OPENAI` | OpenAI model name | `gpt-4o` |
| `OPEN_API` | OpenAI API key | Required for OpenAI |

### Model Configuration Summary

| Role | Model | API |
|------|-------|-----|
| Old script generation | gpt-4o-mini | OpenAI |
| New script generation | gpt-4.1-mini | OpenAI |
| Template classification | gpt-4o-mini | OpenAI |
| Judge (primary) | Kimi K2 Thinking | Bedrock |
| Judge (alternate) | gpt-4o / gpt-5.2 | OpenAI |

---

## Prompt Management

### List Registered Prompts

```bash
python -m evaluator prompts list
```

Output:
```
Registered prompt versions:
  legacy-v1.0    [per-type]  draft   gpt-4o-mini   Prompt version legacy-v1.0
  unified-v2.1   [unified]   draft   gpt-4.1-mini  Prompt version unified-v2.1
```

### View Prompt Details

```bash
python -m evaluator prompts show legacy-v1.0
```

### Register a New Prompt

```bash
# Unified prompt (single file)
python -m evaluator prompts register \
  --id unified-v3.0 \
  --type unified \
  --model gpt-4.1-mini \
  --file prompts/unified/unified_v3.txt \
  --description "Improved unified prompt with better hooks"

# Per-type prompt (directory of files)
python -m evaluator prompts register \
  --id legacy-v2.0 \
  --type per-type \
  --model gpt-4o-mini \
  --dir prompts/legacy_v2/ \
  --description "Updated legacy prompts"
```

### Update Prompt Status

```bash
python -m evaluator prompts set-status unified-v2.1 active
```

Status options: `draft`, `active`, `deprecated`

### Delete a Prompt

```bash
python -m evaluator prompts delete unified-v2.1
```

---

## Running Evaluations

### Basic Run

```bash
python -m evaluator run --prompt unified-v2.1
```

This will:
1. Load the test suite from `data/test_suite.json`
2. Show cost estimate and ask for confirmation
3. Generate scripts using the specified prompt
4. Score each script across 7 dimensions
5. Save results to `data/runs/<run_id>.json`

### Run Options

```bash
python -m evaluator run --prompt unified-v2.1 \
  --auto-approve \           # Skip confirmation prompt
  --resume \                 # Resume from last checkpoint
  --max-inputs 10 \          # Limit to first N test inputs
  --test-suite custom.json   # Use custom test suite
```

### Output

```
================================================================================
Evaluation Run: run_unified-v2.1_20260225_143022
================================================================================
Prompt Version: unified-v2.1
Test Suite:     data/test_suite.json (42 inputs)
Judge Provider: bedrock (moonshot.kimi-k2-thinking)
================================================================================

Cost Estimate:
  Generation:  ~$0.12 (42 scripts)
  Judging:     ~$2.10 (42 scripts x 7 dimensions)
  Total:       ~$2.22

Proceed? [y/N]: y

[1/42] Evaluating: How to Make Perfect Fried Rice (Explainer, YouTube, 2min)
       Generating script... OK (847 chars)
       Scoring: timing_accuracy=8, template_compatibility=9, hook_quality=7...
       Composite: 7.86

[2/42] Evaluating: ...
```

### Resume After Failure

If a run crashes, resume from the last checkpoint:

```bash
python -m evaluator run --prompt unified-v2.1 --resume
```

---

## Comparing Runs

### Compare Two Runs

```bash
python -m evaluator compare \
  --run1 run_legacy-v1.0_20260225_100000 \
  --run2 run_unified-v2.1_20260225_143022 \
  --output comparison_report.md
```

### Comparison Output

The comparison report includes:

1. **Overall Score Change**
   - Mean composite score for each run
   - Delta and statistical significance (p-value)
   - Classification: IMPROVED, REGRESSION, or NO_CHANGE

2. **Per-Dimension Analysis**
   - Score changes for each of the 7 dimensions
   - Which dimensions improved or regressed

3. **Feedback Theme Diff**
   - Resolved issues (present in run1, not in run2)
   - Persistent issues (still present)
   - New issues (appeared in run2)

### Example Output

```markdown
## Script Quality Comparison

| Metric | legacy-v1.0 | unified-v2.1 | Delta | Significance |
|--------|-------------|--------------|-------|--------------|
| Script Quality | 3.42 | 3.91 | +0.49 | IMPROVED (p=0.0023) |

### Script Quality Dimensions

| Dimension | Run 1 | Run 2 | Delta | Status |
|-----------|-------|-------|-------|--------|
| Hook Quality | 3.2 | 4.1 | +0.9 | IMPROVED (p=0.012) |
| Tone Match | 3.5 | 3.8 | +0.3 | NO_CHANGE |
| Structural Flow | 3.6 | 3.9 | +0.3 | NO_CHANGE |
| Content Richness | 3.3 | 3.7 | +0.4 | IMPROVED (p=0.041) |
| Completeness | 3.5 | 4.0 | +0.5 | IMPROVED (p=0.028) |

## System Metrics Comparison

| Metric | Run 1 | Run 2 | Delta |
|--------|-------|-------|-------|
| Timing Accuracy | 4.1 | 4.3 | +0.2 |
| Template Compatibility | 3.2 | 3.5 | +0.3 |
```

---

## Understanding Results

### Run Result Structure

Each run produces a JSON file in `data/runs/`:

```json
{
  "run_id": "run_unified-v2.1_20260225_143022",
  "prompt_version": "unified-v2.1",
  "timestamp": "2026-02-25T14:30:22",
  "results": [
    {
      "script_id": "input_001",
      "test_input": { "subject": "...", "category": "..." },
      "generated_script": "...",
      "scores": {
        "timing_accuracy": { "score": 8, "feedback": "..." },
        "template_compatibility": { "score": 9, "feedback": "..." },
        ...
      },
      "composite_score": 7.86
    }
  ],
  "summary": {
    "total_inputs": 42,
    "successful": 42,
    "failed": 0,
    "mean_composite": 7.31
  }
}
```

### Aggregation Results

Aggregation files (`<run_id>_aggregation.json`) contain:

- **Overall statistics**: mean, median, std, min, max per dimension
- **Breakdowns**: by video_type, duration_range, platform
- **Feedback themes**: clustered common issues with counts

### Statistical Significance

The comparison uses the **Wilcoxon signed-rank test**:

- **p < 0.05**: Statistically significant difference
- **delta >= 0.3**: Meaningful score change

A dimension is classified as:
- **IMPROVED**: delta >= +0.3 AND p < 0.05
- **REGRESSION**: delta <= -0.3 AND p < 0.05
- **NO_CHANGE**: otherwise

---

## File Structure

```
Eval-Judge/
├── .env                          # Environment configuration
├── .env-example                  # Template for .env
├── EVALUATION-JUDGE.md           # This documentation
│
├── evaluator/                    # Main package
│   ├── __init__.py
│   ├── __main__.py               # Entry point for python -m evaluator
│   ├── prompt_registry.py        # Prompt version management
│   ├── run.py                    # Evaluation runner
│   ├── aggregate.py              # Score aggregation
│   ├── compare.py                # Run comparison
│   ├── report.py                 # Report generation
│   └── cli.py                    # CLI interface
│
├── scorers/                      # Individual scoring modules
│   ├── timing_accuracy.py
│   ├── template_compatibility.py
│   ├── hook_quality.py
│   ├── tone_match.py
│   ├── structural_flow.py
│   ├── content_richness.py
│   └── completeness.py
│
├── prompts/                      # Prompt files
│   ├── legacy/                   # Per-type prompts
│   │   ├── explainer.txt
│   │   ├── marketing.txt
│   │   ├── tutorial.txt
│   │   ├── internal_comms.txt
│   │   └── product_intro.txt
│   └── unified/                  # Unified prompts
│       └── unified_v1.txt
│
├── data/
│   ├── test_suite.json           # Test inputs
│   ├── prompt_versions.json      # Prompt registry
│   └── runs/                     # Evaluation results
│       ├── run_<id>.json
│       ├── run_<id>_aggregation.json
│       └── compare_<id1>_vs_<id2>.json
│
└── scripts/
    └── test_bedrock.py           # Bedrock connectivity test
```

---

## Scoring Dimensions

Scripts are evaluated on 7 dimensions (1-5 scale), split into two categories:

### Script Quality (LLM-Judged)

These 5 dimensions are averaged equally to produce the **Script Quality** score:

| Dimension | What It Measures |
|-----------|------------------|
| **hook_quality** | Is the opening hook engaging and attention-grabbing? |
| **tone_match** | Does the tone match the requested style and platform? |
| **structural_flow** | Does the script flow logically from section to section? |
| **content_richness** | Is the content substantive, specific, and valuable? |
| **completeness** | Are all required sections present (Hook, Intro, Steps, CTA, etc.)? |

### System Metrics (Deterministic)

These 2 dimensions are reported separately as **System Metrics**:

| Metric | What It Measures |
|--------|------------------|
| **timing_accuracy** | Does script length match requested duration? (~140 WPM) |
| **template_compatibility** | Does output format match Pictory template requirements? |

### Score Reporting

Reports display scores in two sections:

```markdown
## Script Quality: 3.7 / 5

| Dimension | Score |
|-----------|-------|
| Hook Quality | 3.9 |
| Tone Match | 3.6 |
| Structural Flow | 3.8 |
| Content Richness | 3.5 |
| Completeness | 3.7 |

## System Metrics

| Metric | Score |
|--------|-------|
| Timing Accuracy | 4.3 / 5 |
| Template Compatibility | 3.4 / 5 |
```

### Comparison Behavior

- **Script Quality**: Uses Wilcoxon signed-rank test for statistical significance
- **System Metrics**: Simple mean delta comparison (no statistical test)

---

## Models Used

### Script Generation

| Prompt Type | Model | Why |
|-------------|-------|-----|
| Per-type (legacy) | gpt-4o-mini | Original production model |
| Unified (new) | gpt-4.1-mini | Newer model for unified prompts |

### Judge Model

| Provider | Model | Notes |
|----------|-------|-------|
| Bedrock (primary) | Kimi K2 Thinking | Strong reasoning, cost-effective |
| OpenAI (alternate) | gpt-4o | Fallback option |

### Template Classification

| Model | Purpose |
|-------|---------|
| gpt-4o-mini | Classify video type when not explicitly provided |

---

## Troubleshooting

### "Bedrock client creation failed"

1. Check AWS credentials:
   ```bash
   aws sts get-caller-identity --profile your-profile
   ```

2. Verify model access in AWS console (Bedrock → Model access)

3. Check region - Kimi K2 may only be available in specific regions

### "NumPy version conflict"

The scipy import may fail with NumPy 2.x. The code uses lazy imports to avoid this, but if issues persist:

```bash
pip install "numpy<2.0"
```

### "No matching test inputs found between runs"

Ensure both runs used the same test suite. The comparison matches results by `script_id`.

### Cost is too high

- Use `--max-inputs N` to test with fewer inputs
- Use `--test-suite` with a smaller custom test file

### Run crashed mid-way

Use `--resume` to continue from the last checkpoint:

```bash
python -m evaluator run --prompt unified-v2.1 --resume
```

---

## Quick Reference

### Running Evaluations

```bash
# List available prompts
python -m evaluator prompts list

# Run legacy prompt (historical mode - $0 generation cost)
python -m evaluator run --prompt legacy-v1.0 -a

# Run unified prompt (live generation)
python -m evaluator run --prompt unified-v2.1 -a

# Limit to N inputs (for testing)
python -m evaluator run --prompt unified-v2.1 --max-inputs 5 -a

# Resume from last checkpoint after crash
python -m evaluator run --prompt unified-v2.1 --resume
```

### Comparing Runs

```bash
# Compare two evaluation runs (don't include .json extension)
python -m evaluator compare --run1 eval-legacy-v1.0-YYYYMMDD-HHMMSS --run2 eval-unified-v2.1-YYYYMMDD-HHMMSS

# Generate markdown report for a single run (saves to data/runs/<run_id>_report.md)
python -m evaluator report --run <run_id>

# Print report to stdout
python -m evaluator report --run <run_id> --print
```

### Other Commands

```bash
# Test Bedrock connectivity
python scripts/test_bedrock.py

# View prompt details
python -m evaluator prompts show legacy-v1.0
```

### Typical Workflow

```bash
# 1. Run legacy baseline (uses historical scripts)
python -m evaluator run --prompt legacy-v1.0 -a

# 2. Run new unified prompt (generates scripts live)
python -m evaluator run --prompt unified-v2.1 -a

# 3. Compare the two runs
python -m evaluator compare --run1 <legacy-run-id> --run2 <unified-run-id>
```

Results are saved in `data/runs/` as JSON files.

---

## Contributing

When adding new features:

1. **New Scorer**: Add to `scorers/` and update `DIMENSIONS` in `compare.py`
2. **New Prompt Type**: Update `prompt_registry.py` and add loading logic
3. **New CLI Command**: Add subparser in `cli.py`

---

*Documentation generated for Pictory.ai Script Evaluation System v1.0*
