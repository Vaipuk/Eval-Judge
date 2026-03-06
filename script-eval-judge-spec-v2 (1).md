# Pictory.ai Script Generation Evaluation System

## Full Specification & Implementation Plan — v2

---

## 1. Executive Summary

Pictory.ai's script generation feature takes a user-provided topic and produces a video script, guided by a system prompt tailored to the video type (Explainer, Marketing, Internal Comms, Tutorial, Product Intro). A downstream **Smart Template** system classifies each script line into visual layout categories (TITLE, SECTION, NUMBER, QUOTE, LIST, EMPHASIS, DEFAULT) for video rendering.

Recent prompt engineering unified multiple per-type system prompts into a single comprehensive prompt, reducing timing variance from ±1–2 minutes to ±15 seconds. This system provides the **quantifiable, repeatable evaluation framework** to:

- Prove prompt improvements with measurable scores
- Catch regressions before they hit production
- Guide prompt iteration with actionable feedback
- Give the team a shared, accessible quality dashboard

The approach uses a **Chain-of-Thought LLM Judge** with a highly detailed rubric — no human-labeled Golden Set required. Trust comes from rubric specificity and spot-checkable reasoning, not statistical calibration.

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                     PROMPT EVALUATOR (orchestrator)                   │
│                                                                      │
│  Input: System prompt version to test                                │
│  Test Suite: Real user inputs from cleaned production data           │
│                                                                      │
│  For each test input:                                                │
│  ┌────────────┐    ┌────────────┐    ┌─────────────────────────────┐ │
│  │ Test Input  │───▶│ Script Gen │───▶│         THE JUDGE           │ │
│  │ (topic,     │    │ (prompt    │    │                             │ │
│  │  type,      │    │  under     │    │  Deterministic:             │ │
│  │  duration,  │    │  test)     │    │    • Timing accuracy        │ │
│  │  platform)  │    │            │    │    • Smart Template compat  │ │
│  └────────────┘    └────────────┘    │                             │ │
│                                      │  LLM CoT Judge:             │ │
│                                      │    • Hook quality            │ │
│                                      │    • Tone & style match      │ │
│                                      │    • Structural flow         │ │
│                                      │    • Content richness        │ │
│                                      │    • Completeness            │ │
│                                      │                             │ │
│                                      │  Output per script:         │ │
│                                      │    • 7 sub-scores (1-5)     │ │
│                                      │    • Composite score         │ │
│                                      │    • CoT reasoning           │ │
│                                      │    • Improvement feedback    │ │
│                                      └──────────────┬──────────────┘ │
│                                                     │                │
│  ┌──────────────────────────────────────────────────▼──────────────┐ │
│  │                    AGGREGATION & COMPARISON                     │ │
│  │                                                                  │ │
│  │  • Aggregate scores across test suite (mean, median, std)        │ │
│  │  • Breakdowns by video type, duration, platform                  │ │
│  │  • Compare vs previous prompt version (deltas + significance)    │ │
│  │  • Cluster feedback into themes, rank by frequency               │ │
│  │  • Generate eval report                                          │ │
│  └──────────────────────────────────────────────────┬──────────────┘ │
│                                                     │                │
│  ┌──────────────────────────────────────────────────▼──────────────┐ │
│  │                    STREAMLIT DASHBOARD                           │ │
│  │                                                                  │ │
│  │  • Single run report (scores + radar chart + feedback themes)    │ │
│  │  • Prompt comparison (side-by-side deltas)                       │ │
│  │  • Filters by video type / duration / platform                   │ │
│  │  • Historical trends                                             │ │
│  │  • Script-level drilldown with CoT reasoning                     │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Foundation

### 3.1 Source

Production data lives in S3 bucket `pictory-prod-copilot-response`. Each script generation has a **request file** at `data/{id}.json` containing both input and output:

```json
{
  "error": null,
  "data": {
    "prompt": [
      { "role": "system", "content": "<system prompt with video type, tone, duration formula>" },
      { "role": "user", "content": "<topic> \n\nduration: {range} \n\nplatform: {platform} \n\nsubject: {topic}" }
    ],
    "operation": "create",
    "chunk": "<generated script>",
    "input_cost": 0.00006,
    "output_cost": 0.00015,
    "total_cost": 0.00021,
    "credits_consumed": 1.261,
    "article_response_id": null
  }
}
```

### 3.2 Cleaned Record Schema

After extraction and cleaning, each record looks like:

```json
{
  "id": "000050d0-cfac-4303-b27b-6b13de4d8cee",
  "valid": true,
  "english": true,
  "video_type": "Tutorial",
  "subject": "Kaspa",
  "duration_range": "1min",
  "duration_min_sec": 60,
  "duration_max_sec": 60,
  "duration_midpoint_sec": 60,
  "platform": "YouTube",
  "script": "...",
  "word_count": 131,
  "char_count": 849,
  "estimated_time_sec": 56.1
}
```

### 3.3 How the Data Is Used

The cleaned dataset serves as the **test suite input bank**. For evaluation:
- Strip out the old generated scripts
- Keep only the inputs: `video_type`, `subject`, `duration_range`, `duration_min_sec`, `duration_max_sec`, `platform`
- When evaluating a prompt version, re-run these inputs through the prompt under test
- Judge the freshly generated output
- Same inputs across prompt versions = comparable scores

---

## 4. The Judge — Detailed Design

### 4.1 Scoring Overview

| # | Dimension | Method | Weight | Why |
|---|-----------|--------|--------|-----|
| 1 | Timing Accuracy | Deterministic | 20% | Core requirement; was the primary user complaint |
| 2 | Smart Template Compatibility | Deterministic + programmatic | 20% | Directly impacts video rendering quality |
| 3 | Hook & Opening Quality | LLM CoT | 10% | Drives viewer retention |
| 4 | Tone & Style Match | LLM CoT | 15% | Core to product value proposition |
| 5 | Structural Flow & Coherence | LLM CoT | 15% | Affects video watchability |
| 6 | Content Richness & Specificity | LLM CoT | 10% | Drives template diversity and info value |
| 7 | Completeness & Closure | LLM CoT | 10% | Ensures polished final product |

**Composite score:**
```
overall = (0.20 × timing) + (0.20 × template) + (0.10 × hook)
        + (0.15 × tone) + (0.15 × flow) + (0.10 × richness)
        + (0.10 × completeness)
```

### 4.2 Deterministic Scorer: Timing Accuracy

**Input:** `word_count`, `duration_min_sec`, `duration_max_sec`
**Constant:** ~150 WPM (calibrate against actual Pictory video output)

```python
estimated_duration_sec = (word_count / WPM) * 60

if duration_min_sec <= estimated_duration_sec <= duration_max_sec:
    # Within the requested range
    deviation = 0
else:
    # How far outside the range
    deviation = min(
        abs(estimated_duration_sec - duration_min_sec),
        abs(estimated_duration_sec - duration_max_sec)
    )
```

| Score | Criteria |
|-------|----------|
| 5 | Within requested duration range |
| 4 | Within 15 seconds outside range |
| 3 | Within 30 seconds outside range |
| 2 | Within 60 seconds outside range |
| 1 | More than 60 seconds outside range |

**Note:** Duration is a range (e.g., "1min - 5min"), not an exact target. The range bounds define the acceptable window. Some records have tight ranges (e.g., "1min" maps to `min=60, max=60`), others are wide.

### 4.3 Deterministic Scorer: Smart Template Compatibility

**Process:**
1. Run the generated script through the Smart Template classifier prompt (the Video Script Analyzer)
2. Parse the JSON output to get per-scene category assignments
3. Score programmatically based on:

**Metrics extracted:**

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Category coverage | All 7 types triggered | Count distinct categories |
| TITLE placement | First scene | Check `scenes[0].category == "TITLE"` |
| SECTION spacing | Every 8-12 scenes | Check gaps between SECTION scenes |
| LIST numbering | Sequential, resets on topic change | Validate number sequences |
| Scene count match | Input lines = output scenes | Compare counts |
| Distribution alignment | Per the target percentages below | Calculate deviation |

**Target distribution:**
- TITLE: 5-10%
- SECTION: 10-15%
- LIST: 15-20%
- NUMBER: 10-15%
- QUOTE: 10-15%
- EMPHASIS: 5-10%
- DEFAULT: 35-45%

**Scoring:**

| Score | Criteria |
|-------|----------|
| 5 | 6-7 categories triggered; TITLE at start; SECTIONs well-spaced; distribution within target ranges |
| 4 | 5-6 categories; minor distribution skew; TITLE correct |
| 3 | 4-5 categories; noticeable distribution issues OR TITLE misplaced |
| 2 | 3-4 categories; heavy DEFAULT skew (>60%) |
| 1 | Fewer than 3 categories; almost entirely DEFAULT; structural issues |

### 4.4 LLM CoT Judge — Rubric

The LLM judge evaluates 5 subjective dimensions. Each dimension is assessed in a **separate API call** to avoid cross-contamination. The judge uses chain-of-thought reasoning anchored to specific, observable criteria.

---

#### Dimension 3: Hook & Opening Quality

**The judge receives:** First 3 lines of the script + video type + subject

**Rubric:**

| Score | Criteria | Observable Indicators |
|-------|----------|----------------------|
| 5 — Exceptional | Immediately compelling; creates curiosity or urgency; clearly establishes the video's value proposition; tailored to the specific topic | Uses a surprising fact, provocative question, or vivid scenario specific to the subject; viewer immediately knows what they'll learn/gain; opening could NOT be swapped to a different topic without rewriting |
| 4 — Strong | Engages the viewer; clear topic introduction; some specificity | References the subject directly; creates mild curiosity; establishes context but hook isn't uniquely compelling |
| 3 — Adequate | States the topic but doesn't create strong engagement | Generic question format ("Have you ever wondered about X?"); topic is named but no unique angle; functional but forgettable |
| 2 — Weak | Generic or overly broad; doesn't hook the viewer | Could apply to almost any topic in the same video type; no curiosity trigger; starts with a definition or dictionary-style opening |
| 1 — Poor | No discernible hook; jumps into content without framing; confusing | No opening frame at all; starts mid-explanation; topic is unclear from the first 3 lines |

---

#### Dimension 4: Tone & Style Match

**The judge receives:** Full script + video type + platform

**Tone expectations by video type:**

| Video Type | Expected Tone | Key Indicators |
|------------|---------------|----------------|
| Explainer | Clear, educational, accessible, balanced pacing | Defines terms when introduced; uses analogies; avoids jargon or explains it; maintains a teacher-like voice |
| Marketing | Persuasive, energetic, benefit-focused, CTA-driven | Emphasizes benefits over features; creates urgency; uses power words; has a clear value proposition; strong CTA |
| Internal Comms | Professional, concise, action-oriented, informative | Business-appropriate language; clear action items; respects reader's time; avoids fluff; states impact |
| Tutorial | Instructional, step-by-step, patient, precise | Uses sequential language (first, next, then); each step is actionable; prerequisites stated; no assumed knowledge |
| Product Intro | Enthusiastic, feature-focused, benefit-driven, demo-friendly | Showcases capabilities; connects features to user problems; builds excitement; includes use cases |

**Platform modifiers:**

| Platform | Modifier |
|----------|----------|
| YouTube | Can be longer-form; more detailed; conversational |
| Instagram Reels | Punchy; fast-paced; visual cues; immediate hook |
| TikTok | Ultra-concise; trend-aware; casual tone |
| LinkedIn | Professional; thought-leadership angle; industry terms acceptable |
| General/Other | Default to the video type tone |

**Rubric:**

| Score | Criteria |
|-------|----------|
| 5 | Tone perfectly matches video type AND platform; consistent throughout; no jarring shifts |
| 4 | Tone appropriate with minor inconsistencies (1-2 lines feel off); platform mostly considered |
| 3 | Tone acceptable but noticeably off in sections; platform influence missing |
| 2 | Tone mismatch is distracting (e.g., casual for Internal Comms, dry for Marketing); multiple sections feel wrong |
| 1 | Tone completely wrong for the video type; feels like wrong video type entirely |

---

#### Dimension 5: Structural Flow & Coherence

**The judge receives:** Full script + video type

**Expected structures by video type:**

| Video Type | Expected Arc |
|------------|-------------|
| Explainer | Hook → Problem/Context → Explanation → Examples → Summary → CTA |
| Marketing | Hook → Pain Point → Solution → Benefits → Social Proof → CTA |
| Internal Comms | Context → Key Message → Details → Action Items → Next Steps |
| Tutorial | Overview → Prerequisites → Step-by-Step → Tips → Recap |
| Product Intro | Hook → Problem → Product Overview → Features → Demo Points → CTA |

**Rubric:**

| Score | Criteria | Observable Indicators |
|-------|----------|----------------------|
| 5 | Clear narrative arc matching the video type; smooth transitions; logical progression; strong conclusion | Each section flows naturally to the next; transitional phrases present; no content feels out of place; structure matches expected arc |
| 4 | Good flow with minor awkward transitions; structure mostly matches expected arc | 1-2 transitions feel abrupt; overall arc is correct; minor reordering would improve flow |
| 3 | Acceptable structure but feels choppy or missing clear transitions | Sections exist but transitions are just topic jumps; reader can follow but has to work at it; missing 1 expected section |
| 2 | Disjointed; topics jump without connection; weak conclusion | No transitional language; content blocks feel randomly ordered; missing 2+ expected sections; ending is abrupt |
| 1 | No discernible structure; incoherent flow | Cannot identify an arc; content contradicts itself or repeats; feels like disconnected bullet points |

---

#### Dimension 6: Content Richness & Specificity

**The judge receives:** Full script + video type + subject

**Rubric:**

| Score | Criteria | Observable Indicators |
|-------|----------|----------------------|
| 5 | Rich with specific details, statistics, examples, and expert references; no filler; content is genuinely informative about the specific subject | Contains 3+ concrete data points or examples; references specific names, tools, or methods; someone could learn something new from this script |
| 4 | Good specificity; mostly concrete with minor generic sections | Contains 1-2 concrete data points; most sentences add new information; minor filler present |
| 3 | Mix of specific and generic content | Some concrete details but padded with general statements; feels surface-level; could go deeper |
| 2 | Mostly generic; lacks concrete details or examples | Relies on vague claims ("many people," "studies show"); no specific names, numbers, or examples; feels like a template |
| 1 | Entirely generic and vague; could apply to any topic | Swap the subject name and the script still works for any other topic; pure filler; no information value |

**Smart Template connection:** Content richness directly drives Smart Template diversity. Scripts with numbers trigger NUMBER templates, scripts with quotes trigger QUOTE templates, sequential items trigger LIST templates. The judge should note when generic content limits template variety.

---

#### Dimension 7: Completeness & Closure

**The judge receives:** Last 5 lines of the script + video type + full script length context

**Rubric:**

| Score | Criteria | Observable Indicators |
|-------|----------|----------------------|
| 5 | Natural conclusion; summarizes key points; includes appropriate CTA or closing thought tailored to video type and platform | Summary references specific points from the script; CTA is specific and actionable; feels like a complete piece |
| 4 | Good ending with minor abruptness; CTA present but generic | Summary exists but misses a key point; CTA is present but could be more specific |
| 3 | Ends adequately but feels like it could continue; CTA is vague or missing | Last lines introduce new info instead of wrapping up; generic sign-off; no clear CTA |
| 2 | Abrupt ending; missing summary or CTA; feels unfinished | Script just stops; no wrapping up; last line doesn't feel like a conclusion |
| 1 | Clearly truncated or unfinished; mid-thought ending | Sentence appears cut off; obvious that more content was intended; no conclusion whatsoever |

---

### 4.5 LLM Judge Prompt Template

Each dimension gets a separate API call with this structure:

```
SYSTEM PROMPT:
You are a video script quality evaluator for Pictory.ai, an AI video creation
platform. You evaluate generated scripts on specific quality dimensions using a
strict, detailed rubric.

Your evaluation must be:
- Anchored to the rubric criteria — cite specific observable indicators
- Evidence-based — quote or reference specific lines from the script
- Calibrated — 3 means "meets minimum acceptable bar", 5 means "exceptional,
  no meaningful room for improvement". Use the full 1-5 range.
- Actionable — your improvement suggestions must be specific enough that a
  prompt engineer could act on them

USER PROMPT:
## Task
Evaluate the following video script on the dimension: {DIMENSION_NAME}

## Script Metadata
- Video Type: {video_type}
- Subject: {subject}
- Target Duration: {duration_range}
- Platform: {platform}

## Script
{script_text}

## Rubric
{FULL_RUBRIC_FOR_THIS_DIMENSION}

## Required Output Format (JSON)
Think step by step, then provide your evaluation:

{
  "dimension": "{DIMENSION_NAME}",
  "chain_of_thought": "<your step-by-step reasoning analyzing the script against each rubric level, starting from score 5 and working down until you find the best match>",
  "score": <1-5>,
  "justification": "<2-3 sentence summary of why this score>",
  "evidence": ["<specific line or pattern from script supporting the score>", ...],
  "improvements": ["<specific, actionable suggestion that would raise the score>", ...]
}
```

**Key design decisions:**
- CoT reasoning goes **top-down** (start at 5, work down) to avoid anchoring bias toward low scores
- Each dimension is a separate call to prevent cross-contamination
- Improvements must be specific and actionable (not "make the hook better" but "replace the generic question opener with a surprising statistic about {subject}")

### 4.6 Judge Output Schema (per script)

```json
{
  "script_id": "000050d0-cfac-4303-b27b-6b13de4d8cee",
  "prompt_version": "unified-v2.1",
  "timestamp": "2025-02-23T10:30:00Z",
  "metadata": {
    "video_type": "Tutorial",
    "subject": "Kaspa",
    "duration_range": "1min",
    "platform": "YouTube"
  },
  "scores": {
    "timing_accuracy": {
      "score": 4,
      "estimated_duration_sec": 56.1,
      "target_min_sec": 60,
      "target_max_sec": 60,
      "deviation_sec": 3.9
    },
    "template_compatibility": {
      "score": 3,
      "categories_triggered": ["TITLE", "DEFAULT", "SECTION", "LIST"],
      "category_count": 4,
      "distribution": { "TITLE": 0.08, "SECTION": 0.12, "DEFAULT": 0.56, "LIST": 0.24 },
      "issues": ["No NUMBER scenes despite content opportunities", "DEFAULT > 45% target"]
    },
    "hook_quality": {
      "score": 3,
      "chain_of_thought": "...",
      "justification": "Opens with a question but it's generic...",
      "evidence": ["Are you struggling to understand Kaspa?"],
      "improvements": ["Replace generic question with a specific statistic about Kaspa's transaction speed"]
    },
    "tone_match": { "score": 4, "..." : "..." },
    "structural_flow": { "score": 4, "..." : "..." },
    "content_richness": { "score": 2, "..." : "..." },
    "completeness": { "score": 3, "..." : "..." }
  },
  "composite_score": 3.15,
  "all_improvements": [
    "Replace generic question opener with a specific statistic about Kaspa's transaction speed",
    "Include concrete numbers: Kaspa's TPS, block time, market cap",
    "Add a specific CTA: link to wallet download or community channel",
    "..."
  ]
}
```

### 4.7 Trust & Validation Strategy

Without a human-labeled Golden Set, trust in the judge comes from:

1. **Rubric specificity** — criteria are anchored to observable indicators, not subjective vibes. Two different LLMs given the same rubric should produce similar scores.

2. **CoT transparency** — every score comes with visible reasoning. If the reasoning is wrong, you can see it.

3. **Spot-checking** — periodically review judge output on ~10-20 scripts. Read the CoT, check if you agree. If the reasoning is consistently sound, the scores are trustworthy.

4. **Consistency checks** — run the same script through the judge 3 times. If scores vary by more than 1 point on any dimension, the rubric for that dimension needs tightening.

5. **Deterministic anchoring** — 2 of 7 dimensions (40% of weight) are fully deterministic. These don't drift, hallucinate, or vary between runs.

---

## 5. Feedback Aggregation

### 5.1 Per-Script Feedback

Each script gets an `all_improvements` list — the union of improvement suggestions from all 5 LLM-judged dimensions plus issues from the 2 deterministic scorers.

### 5.2 Run-Level Feedback Themes

After scoring all scripts in a run, aggregate improvements into themes:

**Process:**
1. Collect all `improvements` across all scripts in the run
2. Use an LLM call to cluster them into themes (or use embedding similarity + clustering)
3. Count frequency of each theme
4. Rank by frequency

**Example output:**

```
FEEDBACK THEMES — Prompt v2.1 (120 scripts evaluated)
──────────────────────────────────────────────────────

1. "Hook uses generic question format"              — 47/120 scripts (39%)
   → Affects: Hook Quality
   → Suggestion: Add instructions to vary hook formats (statistic, scenario, bold claim)

2. "No concrete statistics or data points"           — 38/120 scripts (32%)
   → Affects: Content Richness, Template Compatibility (NUMBER)
   → Suggestion: Add "include at least 2 specific statistics" to system prompt

3. "CTA is generic (subscribe/follow)"               — 31/120 scripts (26%)
   → Affects: Completeness
   → Suggestion: Instruct CTA to reference the specific topic and platform

4. "Tutorial scripts missing prerequisites section"  — 12/120 scripts (10%)
   → Affects: Structural Flow (Tutorial type only)
   → Suggestion: Add prerequisite step to Tutorial structure template

5. "Heavy DEFAULT skew in template distribution"     — 28/120 scripts (23%)
   → Affects: Template Compatibility
   → Suggestion: Instruct scripts to include numbered lists, quotes, and statistics
```

### 5.3 How Feedback Drives Prompt Iteration

```
Run eval on Prompt v2.0
        │
        ▼
  Scores + Feedback themes
        │
        ▼
  You read themes, edit the prompt:
    + "Vary hook formats: use statistics, scenarios, or bold claims"
    + "Include at least 2 specific statistics per script"
    + "Tailor CTA to the topic and platform"
        │
        ▼
  Run eval on Prompt v2.1
        │
        ▼
  Compare: Which themes disappeared? (fixed)
           Which are new? (potential regression)
           Which persisted? (needs different approach)
```

This is a **human-in-the-loop** cycle. The feedback informs your prompt edits, but you make the decisions. The evaluator then measures whether your changes worked.

---

## 6. Prompt Evaluator — Orchestrator Design

### 6.1 Evaluation Run Flow

```python
# Pseudocode for a single evaluation run

def run_evaluation(prompt_version, test_suite, config):
    results = []

    for test_input in test_suite:
        # Step 1: Generate script with the prompt under test
        script = generate_script(
            system_prompt=prompt_version.prompt_text,
            user_input=test_input,
            model="gpt-4o-mini"
        )

        # Step 2: Deterministic scores
        timing_score = score_timing(script, test_input)
        template_score = score_template_compatibility(script)

        # Step 3: LLM judge scores (5 parallel calls)
        hook_score = judge_dimension("hook_quality", script, test_input)
        tone_score = judge_dimension("tone_match", script, test_input)
        flow_score = judge_dimension("structural_flow", script, test_input)
        richness_score = judge_dimension("content_richness", script, test_input)
        completeness_score = judge_dimension("completeness", script, test_input)

        # Step 4: Composite
        composite = compute_composite(timing_score, template_score,
                                       hook_score, tone_score, flow_score,
                                       richness_score, completeness_score)

        results.append(Result(script, scores, feedback))

    # Step 5: Aggregate
    aggregate = aggregate_scores(results)
    themes = cluster_feedback(results)

    # Step 6: Compare (if baseline exists)
    comparison = compare_to_baseline(aggregate, config.baseline_run_id)

    # Step 7: Generate report
    report = generate_report(aggregate, themes, comparison)

    return EvalRun(results, aggregate, themes, comparison, report)
```

### 6.2 Test Suite Construction

From the cleaned production dataset:
- Filter to `valid=true`, `english=true`
- Strip out old generated scripts — keep only inputs
- Ensure coverage across all 5 video types
- Include diverse durations and platforms
- Target: ~100-150 test inputs

**Test input schema:**
```json
{
  "id": "test-001",
  "video_type": "Tutorial",
  "subject": "Kaspa",
  "duration_range": "1min",
  "duration_min_sec": 60,
  "duration_max_sec": 60,
  "platform": "YouTube"
}
```

### 6.3 Comparison & Regression Detection

When comparing two runs:

1. Match scripts by test input ID (same input → comparable outputs)
2. Per-dimension: compute mean delta, run paired Wilcoxon signed-rank test
3. Flag **regression** if any dimension drops ≥ 0.3 points with p < 0.05
4. Flag **improvement** if any dimension rises ≥ 0.3 points with p < 0.05
5. Compare feedback theme lists — which themes disappeared, persisted, or are new

**Comparison output:**
```
COMPARISON: unified-v2.1 vs unified-v2.0
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
Feedback themes resolved: "No concrete statistics" (was 32%, now 8%) ✅
Feedback themes new: "Conclusion repeats intro verbatim" (14%) ⚠️
```

### 6.4 Prompt Version Registry

```json
{
  "prompt_versions": [
    {
      "id": "multi-prompt-legacy",
      "description": "Original per-type prompt system",
      "status": "deprecated",
      "date_created": "2024-XX-XX"
    },
    {
      "id": "unified-v1.0",
      "description": "First unified prompt combining all video types",
      "status": "baseline",
      "date_created": "2025-XX-XX"
    },
    {
      "id": "unified-v2.0",
      "description": "Refined with improved timing and template awareness",
      "status": "production",
      "date_created": "2025-XX-XX"
    }
  ]
}
```

---

## 7. Dashboard (Streamlit)

### View 1: Single Run Report
- Composite score displayed prominently
- Radar chart of 7 dimension scores
- Feedback themes table ranked by frequency with counts
- Script-level drilldown: click any script → see all scores, CoT reasoning, specific feedback

### View 2: Prompt Comparison
- Dropdown to select two prompt versions
- Side-by-side bar chart of dimension scores with green/red deltas
- Statistical significance indicators
- Feedback theme diff: resolved vs. new vs. persistent themes

### View 3: Breakdown Filters
- Filter any view by video type, duration range, or platform
- Catch patterns like "great for Marketing but regressed on Tutorials"
- Scatter plot: composite score vs. estimated duration (spot length-dependent issues)

### View 4: Historical Trends
- Line chart of composite score over time
- Prompt version markers on x-axis
- Per-dimension trend lines
- Regression/improvement event annotations

---

## 8. Build Order

### Step 1: Deterministic Scorers
Build the timing accuracy scorer and Smart Template compatibility scorer. These are Python functions, no LLM calls, fully testable.

**Deliverables:**
- `scorers/timing.py` — takes script + duration metadata, returns score 1-5
- `scorers/template_compat.py` — runs Smart Template classifier, analyzes distribution, returns score 1-5
- Unit tests for both

### Step 2: LLM CoT Judge
Design and implement the 5 dimension judge prompts. Test on a handful of scripts and spot-check reasoning.

**Deliverables:**
- `judge/prompts/` — rubric prompts for each dimension
- `judge/evaluate.py` — function that takes a script + metadata, calls all 7 scorers, returns the full judge output schema
- `judge/config.py` — model selection, weights, thresholds

### Step 3: Test Suite Construction
Extract inputs from cleaned production data. Curate for coverage.

**Deliverables:**
- `data/test_suite.json` — ~100-150 test inputs
- `data/test_suite_stats.md` — distribution summary (by type, duration, platform)

### Step 4: Evaluation Pipeline
Build the orchestrator that runs generation → judging → aggregation → comparison.

**Deliverables:**
- `evaluator/run.py` — batch evaluation runner
- `evaluator/aggregate.py` — score aggregation + feedback theme clustering
- `evaluator/compare.py` — cross-run comparison + regression detection
- `evaluator/report.py` — Markdown report generator

### Step 5: Dashboard
Build Streamlit app that reads eval run JSON files and renders the 4 views.

**Deliverables:**
- `dashboard/app.py` — Streamlit application
- `dashboard/views/` — individual view components

---

## 9. Technical Stack

### 9.1 Model Configuration

| Role | Model | API | Rationale |
|------|-------|-----|-----------|
| Old script generation | GPT-4o-mini | OpenAI (`OPEN_API` key) | Legacy production model |
| New script generation | GPT-4.1-mini | OpenAI (`OPEN_API` key) | Current production model |
| **Judge (primary)** | **Kimi K2 Thinking** | **Amazon Bedrock** (`AWS_PROFILE`) | Strong CoT reasoning; cross-family avoids self-grading bias |
| **Judge (alternate)** | **GPT-5.2** | **OpenAI** (`OPEN_API` key) | Switchable for comparison |

### 9.2 API Configuration

All keys and config live in `.env`:

```env
# AWS (for Bedrock + S3)
AWS_PROFILE=Interns-aws-access-284231530171
AWS_DEFAULT_REGION=us-east-2

# OpenAI (for script generation + alternate judge)
OPEN_API=sk-...

# Judge model switch
JUDGE_PROVIDER=bedrock          # "bedrock" or "openai"
JUDGE_MODEL_BEDROCK=moonshot.kimi-k2-thinking   # Bedrock model ID
JUDGE_MODEL_OPENAI=gpt-5.2     # OpenAI alternate judge model
```

### 9.3 Judge Model Switch Implementation

```python
# judge/config.py

import os
from dotenv import load_dotenv
load_dotenv()

JUDGE_PROVIDER = os.getenv("JUDGE_PROVIDER", "bedrock")

def get_judge_client():
    if JUDGE_PROVIDER == "bedrock":
        import boto3
        session = boto3.Session(profile_name=os.getenv("AWS_PROFILE"))
        client = session.client("bedrock-runtime", region_name=os.getenv("AWS_DEFAULT_REGION"))
        model_id = os.getenv("JUDGE_MODEL_BEDROCK", "moonshot.kimi-k2-thinking")
        return BedrockJudge(client, model_id)

    elif JUDGE_PROVIDER == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPEN_API"))
        model_id = os.getenv("JUDGE_MODEL_OPENAI", "gpt-5.2")
        return OpenAIJudge(client, model_id)

    else:
        raise ValueError(f"Unknown JUDGE_PROVIDER: {JUDGE_PROVIDER}")


class BedrockJudge:
    """Judge using Kimi K2 Thinking via Amazon Bedrock."""
    def __init__(self, client, model_id):
        self.client = client
        self.model_id = model_id

    def evaluate(self, system_prompt, user_prompt):
        # Bedrock converse/invoke API call
        ...


class OpenAIJudge:
    """Judge using OpenAI models (GPT-5.2, etc.)."""
    def __init__(self, client, model_id):
        self.client = client
        self.model_id = model_id

    def evaluate(self, system_prompt, user_prompt):
        response = self.client.chat.completions.create(
            model=self.model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content
```

To switch judge models, just change the `.env`:
```bash
# Use Kimi K2.5 via Bedrock (default)
JUDGE_PROVIDER=bedrock

# Switch to GPT-5.2 via OpenAI
JUDGE_PROVIDER=openai
JUDGE_MODEL_OPENAI=gpt-5.2
```

### 9.4 Infrastructure

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python | Matches existing stack; LLM API libraries available |
| Data storage | JSON files (v1) → SQLite (v2 if needed) | Simple; no infra needed |
| Dashboard | Streamlit | Fast to build; Python-native; URL-shareable |
| Smart Template classifier | Existing prompt via API (OpenAI) | Already built; reuse as-is |

---

## 10. Success Criteria

| Criteria | Target |
|----------|--------|
| Judge consistency | Same script scored 3 times → scores vary by ≤ 1 point per dimension |
| Spot-check agreement | Team reviews 20 scripts → agrees with judge reasoning >80% of the time |
| Baseline established | Old prompt system fully scored across all video types |
| Improvement proven | New unified prompt scores statistically higher on composite |
| Regression detection | System catches intentional quality drops in controlled tests |
| Prompt iteration speed | New prompt idea evaluated in < 1 hour (wall clock) |
| Team accessibility | PMs can view results and understand them without engineering help |

---

## 11. Open Questions

1. **WPM calibration:** What is Pictory's actual words-per-minute rate? Needs measurement against real video output.
2. **Non-English scripts:** Excluded from v1 (english=true filter). Plan for v2?
3. **Cost tracking:** Each eval run involves generation + Smart Template classification + 5 judge calls per script. For 120 scripts, estimate cost per run.
4. **Multi-model testing:** Use the eval pipeline to test script generation across different models (GPT-4o, Claude Sonnet, etc.) for cost/quality optimization.
5. **Smart Template co-optimization:** Should the Smart Template classifier prompt also be tuned alongside the script generation prompt?
6. **Feedback loop automation:** Could feedback themes eventually auto-suggest prompt modifications?
