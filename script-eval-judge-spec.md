# Pictory.ai Script Generation Evaluation Judge

## System Specification & Implementation Plan

---

## 1. Executive Summary

Pictory.ai's core script generation feature takes a user-provided topic and produces a full video script, guided by a system prompt tailored to the video type (Explainer, Marketing, Internal Comms, Tutorial, Product Intro). A downstream **Smart Template** system then classifies each script line into visual layout categories (TITLE, SECTION, NUMBER, QUOTE, LIST, EMPHASIS, DEFAULT) for video rendering.

Recent prompt engineering efforts unified multiple per-type system prompts into a single comprehensive prompt, yielding significant improvements — notably reducing timing variance from ±1–2 minutes to ±15 seconds. However, these improvements lack a **quantifiable, repeatable evaluation framework** to:

- Prove the new prompt outperforms the old one across all dimensions
- Catch regressions when future prompt changes are made
- Give the team a shared, objective quality bar for script output

This document specifies the design of an **LLM-based Evaluation Judge** — an offline scoring system that evaluates generated scripts across multiple quality dimensions, compares prompt versions, and surfaces results through an accessible analytics dashboard.

---

## 2. Problem Statement

| Problem | Impact |
|---------|--------|
| No objective quality metric for generated scripts | Can't prove prompt A is better than prompt B |
| No labeled dataset of "good" vs "bad" scripts | No ground truth for evaluation |
| Smart Template compatibility is unmeasured | Scripts may render poorly even if text quality is fine |
| Timing accuracy was inconsistent (now improved, but untracked) | No historical record of improvement |
| Prompt changes go to production without systematic testing | Risk of silent regressions |
| Quality assessment is subjective and manual | Not scalable, not reproducible |

---

## 3. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EVALUATION PIPELINE                         │
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────────────────┐  │
│  │  Test Suite   │───▶│ Script Gen   │───▶│  LLM Judge            │  │
│  │  (inputs +    │    │ (prompt under │    │  (multi-dimensional   │  │
│  │   metadata)   │    │  evaluation)  │    │   scoring)            │  │
│  └──────────────┘    └──────────────┘    └───────┬───────────────┘  │
│                                                   │                  │
│                                          ┌────────▼────────┐        │
│                                          │  Smart Template  │        │
│                                          │  Compatibility   │        │
│                                          │  Checker         │        │
│                                          └────────┬────────┘        │
│                                                   │                  │
│                                          ┌────────▼────────┐        │
│                                          │  Score Aggregator│        │
│                                          │  & Comparator    │        │
│                                          └────────┬────────┘        │
│                                                   │                  │
│                                          ┌────────▼────────┐        │
│                                          │  Dashboard &     │        │
│                                          │  Analytics       │        │
│                                          └─────────────────┘        │
└─────────────────────────────────────────────────────────────────────┘
```

The pipeline has four major phases, each detailed in the sections below:

1. **Data Labeling & Baseline Construction** — build a ground truth dataset
2. **LLM Judge Design** — multi-dimensional scoring rubric + judge prompt
3. **Evaluation Pipeline** — batch runner, comparison engine, regression detection
4. **Dashboard & Reporting** — accessible analytics for the team

---

## 4. Phase 1: Data Labeling & Baseline Construction

### 4.1 Data Inventory

**Available data:**
- Hundreds of historical (user_input, generated_script) pairs
- User-selected video type (Explainer, Marketing, etc.)
- User-requested video length
- Final script at time of "Create Video" (post any manual edits)

**Data limitation:** We only store the script at the point the user hits "Create Video," so we cannot determine how much manual editing occurred between generation and approval. This means historical scripts are **not reliable ground truth** — a high-quality final script may have been heavily edited from a poor generation.

### 4.2 Baseline Labeling Strategy

Given the data limitation above, we use a **two-track approach**:

#### Track A: Golden Set (Manual Labeling) — ~80–120 scripts

A small, high-confidence dataset manually reviewed and scored by the team.

**Process:**
1. Sample scripts stratified across all 5 video types (~16–24 per type)
2. Include a mix of requested video lengths (short, medium, long)
3. Have 2–3 team members independently score each script on the rubric (Section 5)
4. Calculate inter-rater agreement (Cohen's Kappa or similar)
5. Resolve disagreements through discussion; finalize labels
6. This set becomes the **calibration benchmark** — the judge must correlate with human scores on this set before it's trusted

**Selection criteria for the sample:**
- Prioritize scripts where user hit "Create Video" quickly (less likely to have heavy edits) if timestamp data is available
- Include known "bad" examples if the team can recall specific failures
- Include scripts from both the old multi-prompt system and the new unified prompt

#### Track B: LLM-Assisted Bulk Labeling — remaining historical data

Use the calibrated LLM judge (once validated against the Golden Set) to score the full historical dataset. This gives us:
- A broad baseline distribution of quality scores under the old prompt(s)
- Per-video-type baseline breakdowns
- Identification of failure patterns and weak spots

### 4.3 Synthetic Test Suite

In addition to historical data, build a **curated test suite** of diverse inputs:

| Dimension | Examples |
|-----------|----------|
| Video types | 1 of each: Explainer, Marketing, Internal Comms, Tutorial, Product Intro |
| Topic complexity | Simple ("Benefits of drinking water") → Complex ("Comparing CRISPR gene editing techniques") |
| Requested lengths | 1 min, 3 min, 5 min, 8 min, 10 min |
| Edge cases | Very niche topics, multi-language requests, ambiguous topics |
| Cross-category topics | Topics that blend types (e.g., "Product tutorial that's also marketing") |
| Stat-heavy topics | Topics that should trigger NUMBER templates frequently |
| Quote-heavy topics | Topics with known expert opinions, testimonials |

**Target: ~100–150 synthetic test inputs** covering the above matrix. These are reusable across every prompt evaluation run.

---

## 5. Phase 2: LLM Judge Design

### 5.1 Scoring Rubric

The judge evaluates each generated script on **7 sub-dimensions** plus a **composite overall score**. Each sub-score is on a 1–5 scale.

#### Sub-Score 1: Timing Accuracy (1–5)

Evaluates whether the script's word count maps to the user's requested video duration.

| Score | Definition |
|-------|------------|
| 5 | Within ±15 seconds of target duration |
| 4 | Within ±30 seconds |
| 3 | Within ±1 minute |
| 2 | Within ±2 minutes |
| 1 | Off by more than 2 minutes |

**Calculation method:** This is a **deterministic score**, not LLM-judged. Use a words-per-minute (WPM) constant (typically ~150 WPM for narrated video) to convert script word count to estimated duration, then compare to the user's requested length.

```
estimated_duration_sec = (word_count / WPM) * 60
deviation_sec = abs(estimated_duration_sec - target_duration_sec)
```

> **Note:** The WPM constant should be calibrated against actual Pictory video output durations if possible. Different video types may have slightly different pacing.

#### Sub-Score 2: Smart Template Compatibility (1–5)

Evaluates how well the script triggers diverse and appropriate Smart Template categories.

| Score | Definition |
|-------|------------|
| 5 | All 7 category types triggered; distribution matches guidelines (TITLE 5–10%, SECTION 10–15%, LIST 15–20%, NUMBER 10–15%, QUOTE 10–15%, EMPHASIS 5–10%, DEFAULT 35–45%) |
| 4 | 5–6 category types triggered; distribution mostly within guidelines |
| 3 | 4–5 category types triggered; some categories over/under-represented |
| 2 | Only 3–4 categories triggered; heavy skew toward DEFAULT |
| 1 | Fewer than 3 categories triggered; almost entirely DEFAULT |

**Calculation method:** This is a **hybrid score**. Run the actual Smart Template classifier prompt against the generated script, then programmatically analyze the output distribution. The scoring can be fully deterministic based on the distribution analysis.

**Key metrics to extract:**
- Category coverage (how many of the 7 types appear)
- Distribution deviation from target percentages
- Proper TITLE placement (at the beginning)
- SECTION spacing (every 8–12 scenes)
- LIST numbering correctness (sequential, resets on topic change)
- Scene count = input line count (no truncation)

#### Sub-Score 3: Hook & Opening Quality (1–5)

Evaluates the first 2–3 lines of the script for engagement potential.

| Score | Definition |
|-------|------------|
| 5 | Immediately compelling; creates curiosity or urgency; clearly establishes the video's value proposition |
| 4 | Strong opening; engages the viewer; clear topic introduction |
| 3 | Adequate opening; states the topic but doesn't create strong engagement |
| 2 | Weak opening; generic or overly broad; doesn't hook the viewer |
| 1 | No discernible hook; jumps into content without framing; confusing |

**Evaluation method:** LLM-judged. The judge receives the first 3 lines and the video type and assesses hook quality.

#### Sub-Score 4: Tone & Style Match (1–5)

Evaluates whether the script's tone is appropriate for the selected video type.

| Score | Definition |
|-------|------------|
| 5 | Tone perfectly matches the video type conventions |
| 4 | Tone is appropriate with minor inconsistencies |
| 3 | Tone is acceptable but noticeably off in parts |
| 2 | Tone mismatch is distracting (e.g., overly casual for Internal Comms) |
| 1 | Tone is completely wrong for the video type |

**Tone expectations by video type:**

| Video Type | Expected Tone |
|------------|---------------|
| Explainer | Clear, educational, accessible, balanced pacing |
| Marketing | Persuasive, energetic, benefit-focused, CTA-driven |
| Internal Comms | Professional, concise, action-oriented, informative |
| Tutorial | Instructional, step-by-step, patient, precise |
| Product Intro | Enthusiastic, feature-focused, benefit-driven, demo-friendly |

**Evaluation method:** LLM-judged. The judge receives the full script, the video type, and the tone expectations table above.

#### Sub-Score 5: Structural Flow & Coherence (1–5)

Evaluates the logical progression, transitions, and overall narrative arc.

| Score | Definition |
|-------|------------|
| 5 | Clear narrative arc; smooth transitions; logical progression; strong conclusion |
| 4 | Good flow with minor awkward transitions |
| 3 | Acceptable structure but feels choppy or missing clear transitions |
| 2 | Disjointed; topics jump without connection; weak conclusion |
| 1 | No discernible structure; incoherent flow |

**Structural expectations by video type:**

| Video Type | Expected Structure |
|------------|-------------------|
| Explainer | Problem → Context → Explanation → Examples → Summary |
| Marketing | Hook → Pain Point → Solution → Benefits → Social Proof → CTA |
| Internal Comms | Context → Key Message → Details → Action Items → Next Steps |
| Tutorial | Overview → Prerequisites → Step-by-Step → Tips → Recap |
| Product Intro | Hook → Problem → Product Overview → Features → Demo Points → CTA |

**Evaluation method:** LLM-judged.

#### Sub-Score 6: Content Richness & Specificity (1–5)

Evaluates whether the script contains concrete details, numbers, examples, and avoids generic filler.

| Score | Definition |
|-------|------------|
| 5 | Rich with specific details, statistics, examples, and expert references; no filler |
| 4 | Good specificity; mostly concrete with minor generic sections |
| 3 | Mix of specific and generic content |
| 2 | Mostly generic; lacks concrete details or examples |
| 1 | Entirely generic and vague; could apply to any topic |

**Why this matters for Smart Templates:** Content richness directly drives Smart Template diversity. Scripts with numbers trigger NUMBER templates, scripts with quotes trigger QUOTE templates, scripts with sequential items trigger LIST templates. Generic scripts default to DEFAULT for almost every scene.

**Evaluation method:** LLM-judged, with a note to cross-reference against the Smart Template score.

#### Sub-Score 7: Completeness & Closure (1–5)

Evaluates whether the script feels complete and properly concludes.

| Score | Definition |
|-------|------------|
| 5 | Natural conclusion; summarizes key points; includes appropriate CTA or closing thought |
| 4 | Good ending with minor abruptness |
| 3 | Ends adequately but feels like it could continue |
| 2 | Abrupt ending; missing summary or CTA |
| 1 | Clearly truncated or unfinished |

**Evaluation method:** LLM-judged. The judge receives the last 3–5 lines and the video type.

### 5.2 Composite Score Calculation

The overall score is a **weighted average** of the 7 sub-scores:

| Sub-Score | Weight | Rationale |
|-----------|--------|-----------|
| Timing Accuracy | 20% | Core requirement; was the primary complaint |
| Smart Template Compatibility | 20% | Directly impacts video quality; key business metric |
| Hook & Opening Quality | 10% | Important for viewer retention |
| Tone & Style Match | 15% | Core to the product's value proposition |
| Structural Flow & Coherence | 15% | Affects overall video watchability |
| Content Richness & Specificity | 10% | Drives template diversity and information value |
| Completeness & Closure | 10% | Ensures polished final product |

```
overall_score = (0.20 × timing) + (0.20 × template_compat) + (0.10 × hook)
             + (0.15 × tone) + (0.15 × flow) + (0.10 × richness)
             + (0.10 × completeness)
```

> **Note:** Weights should be reviewed and adjusted after initial calibration against the Golden Set. If the team finds that the composite score doesn't correlate with their intuitive sense of quality, the weights are the first thing to tune.

### 5.3 Judge Prompt Design

The LLM judge operates as a **structured evaluator** with the following prompt architecture:

```
SYSTEM PROMPT (Judge):
You are a video script quality evaluator for Pictory.ai, an AI video creation platform.
You evaluate generated video scripts on specific quality dimensions using a strict rubric.

You will receive:
- The user's original input (topic/prompt)
- The selected video type
- The requested video length
- The generated script
- The specific dimension to evaluate
- The scoring rubric for that dimension

You must:
1. Analyze the script against the rubric criteria
2. Provide a score (1-5) with specific justification
3. Quote specific lines from the script that support your score
4. Identify specific improvements that would raise the score

Respond in JSON format:
{
  "dimension": "<dimension_name>",
  "score": <1-5>,
  "justification": "<2-3 sentence explanation>",
  "evidence": ["<specific line or pattern from script>", ...],
  "improvements": ["<specific actionable suggestion>", ...]
}

IMPORTANT:
- Be calibrated: a score of 3 means "acceptable, meets minimum bar"
- A score of 5 means "exceptional, no meaningful room for improvement"
- Use the full range of the scale
- Do not default to giving 4s for everything
```

**Evaluation strategy:** Each LLM-judged dimension is evaluated in a **separate API call** to avoid cross-contamination and keep each assessment focused. The deterministic scores (timing, template compatibility) are calculated programmatically.

### 5.4 Judge Calibration Process

Before the judge is used at scale:

1. Run the judge against the entire Golden Set (~80–120 scripts)
2. Compare judge scores to human scores on each dimension
3. Calculate correlation (Pearson's r or Spearman's ρ) per dimension
4. **Target: r ≥ 0.75 on each dimension** before the judge is considered calibrated
5. If correlation is low on a dimension, iterate on:
   - The rubric definitions (may be ambiguous)
   - The judge prompt (may need more examples or stricter guidelines)
   - The scoring scale (may need recalibration)
6. Include 3–5 few-shot examples in the judge prompt (selected from the Golden Set) showing scores of 1, 3, and 5 for each dimension

---

## 6. Phase 3: Evaluation Pipeline

### 6.1 Pipeline Components

```
┌─────────────────┐
│  Test Suite      │  JSON file: array of test inputs
│  (inputs.json)   │  {topic, video_type, target_length_sec}
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Script Generator│  Calls GPT-4o-mini with the prompt under test
│  Runner          │  Stores: {input, prompt_version, generated_script, timestamp}
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Deterministic   │  Timing score (word count → duration → deviation)
│  Scorers         │  Template score (run Smart Template classifier → analyze distribution)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LLM Judge       │  5 parallel API calls per script (hook, tone, flow, richness, completeness)
│  Scorer          │  Returns per-dimension {score, justification, evidence, improvements}
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Score Aggregator│  Computes composite score per script
│                  │  Aggregates across test suite: mean, median, std, min, max per dimension
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Comparator      │  Compares current run against previous runs / baseline
│                  │  Flags regressions, highlights improvements
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Report Generator│  Produces run summary (JSON + Markdown)
│  & Dashboard     │  Feeds into analytics dashboard
└─────────────────┘
```

### 6.2 Evaluation Run Schema

Each evaluation run produces a structured output:

```json
{
  "run_id": "eval-2025-02-11-001",
  "prompt_version": "unified-v2.3",
  "model": "gpt-4o-mini",
  "timestamp": "2025-02-11T14:30:00Z",
  "test_suite_version": "v1.0",
  "test_count": 120,
  "aggregate_scores": {
    "overall": { "mean": 3.8, "median": 4.0, "std": 0.6, "min": 2.1, "max": 4.9 },
    "timing_accuracy": { "mean": 4.5, "median": 5.0, "std": 0.5, ... },
    "template_compatibility": { "mean": 3.2, "median": 3.0, "std": 0.8, ... },
    "hook_quality": { ... },
    "tone_match": { ... },
    "structural_flow": { ... },
    "content_richness": { ... },
    "completeness": { ... }
  },
  "by_video_type": {
    "Explainer": { "overall": { ... }, "timing_accuracy": { ... }, ... },
    "Marketing": { ... },
    "Internal Comms": { ... },
    "Tutorial": { ... },
    "Product Intro": { ... }
  },
  "by_target_length": {
    "1min": { ... },
    "3min": { ... },
    "5min": { ... },
    "8min": { ... },
    "10min": { ... }
  },
  "regressions": [],
  "improvements": [],
  "individual_results": [ ... ]
}
```

### 6.3 Comparison & Regression Detection

When a new prompt version is evaluated, the comparator:

1. Loads the baseline run (or any specified previous run)
2. Compares aggregate scores on each dimension
3. Flags a **regression** if any dimension's mean score drops by ≥ 0.3 points
4. Flags an **improvement** if any dimension's mean score increases by ≥ 0.3 points
5. Runs a paired t-test or Wilcoxon signed-rank test on per-script scores to determine if differences are statistically significant (p < 0.05)
6. Produces a **comparison summary**:

```
COMPARISON: unified-v2.3 vs unified-v2.2
─────────────────────────────────────────
Overall:              3.8 → 4.1  (+0.3) ✅ IMPROVED (p=0.02)
Timing Accuracy:      4.5 → 4.6  (+0.1)    No significant change
Template Compat:      3.2 → 3.8  (+0.6) ✅ IMPROVED (p=0.001)
Hook Quality:         3.5 → 3.4  (-0.1)    No significant change
Tone Match:           4.0 → 4.1  (+0.1)    No significant change
Structural Flow:      3.7 → 3.9  (+0.2)    No significant change
Content Richness:     3.3 → 3.7  (+0.4) ✅ IMPROVED (p=0.01)
Completeness:         4.0 → 3.6  (-0.4) ⚠️ REGRESSION (p=0.03)
─────────────────────────────────────────
VERDICT: Net improvement, but investigate completeness regression
```

### 6.4 Prompt Version Tracking

Every evaluation run is tied to a specific prompt version. Maintain a prompt registry:

```json
{
  "prompt_versions": [
    {
      "id": "multi-prompt-legacy",
      "description": "Original per-type prompt system (Explainer, Marketing, etc.)",
      "date_created": "2024-XX-XX",
      "status": "deprecated"
    },
    {
      "id": "unified-v1.0",
      "description": "First unified prompt combining all video types",
      "date_created": "2025-XX-XX",
      "status": "baseline"
    },
    {
      "id": "unified-v2.0",
      "description": "Refined unified prompt with improved timing guidelines",
      "date_created": "2025-XX-XX",
      "status": "production"
    }
  ]
}
```

---

## 7. Phase 4: Dashboard & Reporting

### 7.1 Dashboard Views

The dashboard should be a simple web app (or Streamlit/Gradio for rapid development) accessible to the team.

**View 1: Run Overview**
- Latest evaluation run summary
- Overall score trend line across all runs
- Per-dimension score bars (current vs. baseline)

**View 2: Prompt Comparison**
- Side-by-side comparison of any two prompt versions
- Dimension-by-dimension delta chart
- Statistical significance indicators
- Per-video-type breakdown

**View 3: Video Type Drilldown**
- Select a video type → see its performance across all dimensions
- Identify which video types are underperforming
- See specific script examples with low scores + judge justifications

**View 4: Failure Analysis**
- Scripts scoring below 3.0 overall
- Most common failure modes (e.g., "hook is always generic for Explainer videos")
- Judge improvement suggestions aggregated into themes

**View 5: Historical Trends**
- Score trends over time by dimension
- Prompt version change markers on the timeline
- Regression/improvement events

### 7.2 Report Format

Each run automatically generates a Markdown summary report:

```markdown
# Evaluation Report: [prompt_version] — [date]

## Summary
- **Overall Score:** 4.1 / 5.0
- **Scripts Evaluated:** 120
- **vs. Baseline:** +0.3 (statistically significant)

## Dimension Breakdown
| Dimension | Score | vs. Baseline | Status |
|-----------|-------|-------------|--------|
| Timing    | 4.6   | +0.1        | ✅      |
| Template  | 3.8   | +0.6        | ✅      |
| ...       | ...   | ...         | ...    |

## Top Regressions
...

## Top Improvements
...

## Recommendations
...
```

---

## 8. Side Initiative: Video Topic Taxonomy

### 8.1 Purpose

Build a structured taxonomy of video topics and sub-categories so the script generation prompt has richer context about what kind of content to produce.

### 8.2 Proposed Taxonomy Structure

```
Video Type (user-selected)
└── Category (inferred from topic)
    └── Sub-category (inferred from topic)
```

**Example:**

```
Marketing
├── Product Launch
│   ├── SaaS / Software
│   ├── Physical Product
│   └── Service / Offering
├── Brand Awareness
│   ├── Company Story
│   ├── Mission / Values
│   └── Industry Leadership
├── Customer Acquisition
│   ├── Pain Point → Solution
│   ├── Comparison / Alternative
│   └── Use Case Showcase
└── Retention / Upsell
    ├── Feature Update
    ├── Customer Success Story
    └── Loyalty / Community
```

### 8.3 How It Integrates

1. **Classification step:** Before script generation, a lightweight LLM call (or rule-based classifier) maps the user's topic + selected video type to a (category, sub-category) pair.
2. **Prompt enrichment:** The category/sub-category is injected into the script generation prompt, giving the LLM more specific guidance on structure, tone, and expected content patterns.
3. **Evaluation benefit:** The judge can also use taxonomy context — e.g., a "Product Launch > SaaS" marketing video should include a demo walkthrough section, while a "Brand Awareness > Company Story" should focus on narrative.

### 8.4 Building the Taxonomy

1. **Data-driven approach:** Run the existing historical scripts through an LLM with the prompt: "Given this user topic and video type, what category and sub-category does this fall into? Suggest the taxonomy."
2. **Cluster the results:** Identify natural groupings and consolidate into a clean taxonomy.
3. **Human review:** Team reviews and refines the taxonomy.
4. **Target: 4–6 categories per video type, 2–4 sub-categories per category.**

---

## 9. Architecture Decision: Unified Prompt vs. Per-Type Prompts

### 9.1 Current State

The new unified prompt combines all video types into a single system prompt with type-specific sections. This has been uniformly better than the old per-type approach.

### 9.2 Analysis

| Factor | Unified Prompt | Per-Type Prompts |
|--------|---------------|-----------------|
| **Cross-type context** | ✅ LLM sees all types, can handle hybrid topics (e.g., "tutorial that's also marketing") | ❌ Each prompt is siloed; can't blend |
| **Maintenance** | ✅ One prompt to update | ❌ 5+ prompts to keep in sync |
| **Prompt length** | ⚠️ Longer prompt, higher token cost per call | ✅ Shorter, more focused |
| **Specificity** | ⚠️ May sacrifice depth for breadth | ✅ Can go deep on type-specific patterns |
| **Consistency** | ✅ Shared guidelines (timing, structure) are uniform | ⚠️ Risk of drift between prompts |
| **Testing** | ✅ One prompt to evaluate | ❌ Must evaluate 5+ prompts separately |

### 9.3 Recommendation: Hybrid Approach

Use the **unified prompt as the base** but enhance it with the **taxonomy system** (Section 8) to inject type-specific and category-specific context dynamically.

```
┌──────────────────────────────────────────────────┐
│  Unified Base Prompt                              │
│  (timing rules, structural guidelines,            │
│   Smart Template awareness, general quality bar)  │
│                                                    │
│  + Dynamic Injection Block:                        │
│  ┌──────────────────────────────────────────────┐ │
│  │ Video Type: Marketing                         │ │
│  │ Category: Product Launch                      │ │
│  │ Sub-category: SaaS / Software                 │ │
│  │                                                │ │
│  │ Type-specific guidance:                        │ │
│  │ - Open with pain point, not feature list       │ │
│  │ - Include social proof / metrics               │ │
│  │ - End with clear CTA and next steps            │ │
│  │ - Structure: Hook→Problem→Solution→Proof→CTA   │ │
│  └──────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

This gives you:
- The cross-type intelligence of the unified prompt
- The specificity of per-type prompts
- The granularity of taxonomy-informed guidance
- A single codebase with one prompt template + dynamic context

---

## 10. Implementation Roadmap

### Phase 1: Foundation (Weeks 1–2)

- [ ] Define and finalize the scoring rubric (Section 5.1)
- [ ] Build the synthetic test suite (~100–150 inputs)
- [ ] Sample and manually label the Golden Set (~80–120 scripts)
- [ ] Set up prompt version registry and evaluation run storage (JSON/SQLite)

### Phase 2: Judge Development (Weeks 2–4)

- [ ] Implement deterministic scorers (timing accuracy, template compatibility)
- [ ] Design and iterate on LLM judge prompts (one per dimension)
- [ ] Calibrate judge against Golden Set (target r ≥ 0.75)
- [ ] Build few-shot example sets from Golden Set for each dimension

### Phase 3: Pipeline Build (Weeks 3–5)

- [ ] Build the batch evaluation runner (Python script)
- [ ] Implement the score aggregator and comparator
- [ ] Add statistical significance testing for comparisons
- [ ] Generate Markdown evaluation reports automatically
- [ ] Run first full evaluation: old prompt baseline vs. new unified prompt

### Phase 4: Dashboard & Productization (Weeks 5–7)

- [ ] Build dashboard (Streamlit or lightweight web app)
- [ ] Implement the 5 dashboard views (Section 7.1)
- [ ] Add prompt version management UI
- [ ] Document the system for team use

### Phase 5: Taxonomy & Prompt Enhancement (Weeks 6–8)

- [ ] Analyze historical data to build topic taxonomy
- [ ] Design the classification step (LLM or rule-based)
- [ ] Implement dynamic prompt injection
- [ ] Evaluate taxonomy-enhanced prompt vs. current unified prompt using the eval pipeline

---

## 11. Technical Stack Recommendations

| Component | Recommendation | Rationale |
|-----------|---------------|-----------|
| Judge LLM | GPT-4o or Claude Sonnet | More capable than 4o-mini for nuanced quality assessment; cost is acceptable for eval (not per-user) |
| Script generation | GPT-4o-mini | Current production model; keep for consistency |
| Pipeline runner | Python | Simple batch scripting, easy LLM API integration |
| Data storage | SQLite or PostgreSQL | Structured eval results; easy querying |
| Dashboard | Streamlit | Rapid development; Python-native; sharable via URL |
| Report format | Markdown + JSON | Human-readable + machine-parseable |
| Version control | Git | Track prompt versions alongside code |

---

## 12. Success Criteria

The evaluation system is considered successful when:

1. **Judge calibration:** ≥ 0.75 correlation with human scores on all dimensions
2. **Baseline established:** Full scoring of old prompt system across all video types
3. **Improvement proven:** New unified prompt scores statistically significantly higher on composite score
4. **Regression detection:** System catches intentional quality drops in controlled tests
5. **Team adoption:** PMs and engineers can run evaluations and interpret results without assistance
6. **Prompt iteration velocity:** New prompt ideas can be evaluated in < 1 hour (wall clock)

---

## 13. Open Questions & Future Work

1. **WPM calibration:** What is Pictory's actual words-per-minute rate for generated videos? This needs measurement to make the timing scorer accurate.
2. **User satisfaction signal:** Can we eventually correlate eval scores with downstream metrics (video completion rate, user retention, etc.)?
3. **Automated prompt optimization:** Once the eval pipeline is stable, explore using it as a reward signal for automated prompt search (e.g., DSPy, prompt evolution).
4. **Multi-model evaluation:** Test script generation across different models (GPT-4o, Claude Sonnet, etc.) to find optimal cost/quality tradeoff.
5. **Smart Template co-optimization:** Should the Smart Template classifier prompt also be tuned alongside the script generation prompt?
