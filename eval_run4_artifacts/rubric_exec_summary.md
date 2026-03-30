# Executive Summary — Rubric

**Task:** Summarize a 2,000-word technical blog post into a 3-bullet executive summary
**Domain:** summarization
**Total Points:** 38
**Pass Threshold:** 85%

---

## sum_compression

**Category:** structure

**Description:** Achieves 20:1+ compression — exactly 3 bullets, each 1-2 sentences

**Pass Condition:** Exactly 3 bullets. Each bullet is 1-2 sentences. Total under 100 words. No filler or hedging.

**Scoring Method:** WEIGHTED_COMPONENTS (max 10 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| bullet_count | Exactly 3 bullets | 0.30 | 1.0 if exactly 3, 0.5 if 2 or 4, 0.0 if other |
| bullet_density | Each bullet is 1-2 sentences, no filler | 0.35 | % of bullets that are 1-2 tight sentences |
| total_length | Total under 100 words | 0.35 | 1.0 if ≤100 words, 0.7 if ≤130, 0.3 if ≤160, 0.0 if >160 |

**Pass Examples:** 3 bullets, 85 words total, each bullet one declarative sentence + one supporting

**Fail Examples:** 5 bullets, 200 words, mini-paragraphs disguised as bullets

---

## sum_fidelity

**Category:** accuracy

**Description:** Bullets capture the actual thesis and key claims — no hallucination

**Pass Condition:** Bullet 1 = core thesis/finding. Bullet 2 = key evidence or mechanism. Bullet 3 = implication or so-what. All traceable to source text.

**Scoring Method:** WEIGHTED_COMPONENTS (max 12 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| thesis_capture | First bullet nails the core thesis | 0.40 | 1.0 if captures central claim, 0.5 if tangential, 0.0 if wrong |
| evidence_capture | Key supporting evidence or mechanism included | 0.30 | 1.0 if strongest evidence cited, 0.5 if secondary, 0.0 if missing |
| no_hallucination | Nothing claimed that isn't in the source | 0.30 | 1.0 if all claims traceable, 0.0 per hallucinated claim |

**Pass Examples:** Thesis + strongest data point + strategic implication, all from source

**Fail Examples:** Vague paraphrase that could describe any post on the topic

---

## sum_exec_value

**Category:** utility

**Description:** An executive could make a decision or take action from these 3 bullets alone

**Pass Condition:** Answers 'so what?' and 'what do I do with this?'. Quantifies where possible. Uses declarative framing, not passive/descriptive.

**Scoring Method:** WEIGHTED_COMPONENTS (max 10 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| actionability | Reader knows what to do or think differently after reading | 0.40 | 1.0 if clear action/decision implication, 0.5 if informational, 0.0 if academic |
| quantification | Numbers, magnitudes, or concrete specifics included | 0.30 | 1.0 if key numbers preserved, 0.5 if qualitative only, 0.0 if vague |
| declarative_framing | Bullets state claims, not 'the post discusses...' | 0.30 | 1.0 if all declarative, 0.5 if mixed, 0.0 if all descriptive/passive |

**Pass Examples:** "LLM inference costs dropped 90% in 18 months — implications for build-vs-buy decisions in 2026"

**Fail Examples:** "The author discusses various aspects of LLM cost trends"

---

## sum_standalone

**Category:** clarity

**Description:** Summary is self-contained — no context needed to understand it

**Pass Condition:** Doesn't reference 'the post' or 'the author'. Defines any jargon. A reader with no context gets the point.

**Scoring Method:** PENALTY_BASED (max 6 pts)

| Penalty | Points Deducted |
|---|---|
| references_source | -2.0 |
| undefined_jargon | -1.5 |
| assumes_context | -1.5 |
| passive_voice_dominant | -1.0 |

**Pass Examples:** Self-contained claims that work as standalone intelligence

**Fail Examples:** "The author argues that..." or "This post explores..."
