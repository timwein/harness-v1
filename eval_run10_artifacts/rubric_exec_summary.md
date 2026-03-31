# Rubric: summarization

**Task:** Summarize a 2,000-word technical blog post into a 3-bullet executive summary

**Domain:** summarization
**Total Points:** 38
**Pass Threshold:** 85%
**Criteria Count:** 4
**Generated:** 2026-03-31 05:56:05 UTC

---

## 1. sum_compression

**Category:** structure
**Description:** Achieves 20:1+ compression — exactly 3 bullets, each 1-2 sentences

**Pass Condition:** Exactly 3 bullets. Each bullet is 1-2 sentences. Total under 100 words. No filler or hedging.

**Scoring Method:** `weighted_components`
**Max Points:** 10

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `bullet_count` | 30% | Exactly 3 bullets | 1.0 if exactly 3, 0.5 if 2 or 4, 0.0 if other |
| `bullet_density` | 35% | Each bullet is 1-2 sentences, no filler | % of bullets that are 1-2 tight sentences |
| `total_length` | 35% | Total under 100 words | 1.0 if ≤100 words, 0.7 if ≤130, 0.3 if ≤160, 0.0 if >160 |

### Pass Examples

- 3 bullets, 85 words total, each bullet one declarative sentence + one supporting

### Fail Examples

- 5 bullets, 200 words, mini-paragraphs disguised as bullets

---

## 2. sum_fidelity

**Category:** accuracy
**Description:** Bullets capture the actual thesis and key claims — no hallucination

**Pass Condition:** Bullet 1 = core thesis/finding. Bullet 2 = key evidence or mechanism. Bullet 3 = implication or so-what. All traceable to source text.

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `thesis_capture` | 40% | First bullet nails the core thesis | 1.0 if captures central claim, 0.5 if tangential, 0.0 if wrong |
| `evidence_capture` | 30% | Key supporting evidence or mechanism included | 1.0 if strongest evidence cited, 0.5 if secondary, 0.0 if missing |
| `no_hallucination` | 30% | Nothing claimed that isn't in the source | 1.0 if all claims traceable, 0.0 per hallucinated claim |

### Pass Examples

- Thesis + strongest data point + strategic implication, all from source

### Fail Examples

- Vague paraphrase that could describe any post on the topic

---

## 3. sum_exec_value

**Category:** utility
**Description:** An executive could make a decision or take action from these 3 bullets alone

**Pass Condition:** Answers 'so what?' and 'what do I do with this?'. Quantifies where possible. Uses declarative framing, not passive/descriptive.

**Scoring Method:** `weighted_components`
**Max Points:** 10

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `actionability` | 40% | Reader knows what to do or think differently after reading | 1.0 if clear action/decision implication, 0.5 if informational, 0.0 if academic |
| `quantification` | 30% | Numbers, magnitudes, or concrete specifics included | 1.0 if key numbers preserved, 0.5 if qualitative only, 0.0 if vague |
| `declarative_framing` | 30% | Bullets state claims, not 'the post discusses...' | 1.0 if all declarative, 0.5 if mixed, 0.0 if all descriptive/passive |

### Pass Examples

- 'LLM inference costs dropped 90% in 18 months — implications for build-vs-buy decisions in 2026'

### Fail Examples

- 'The author discusses various aspects of LLM cost trends'

---

## 4. sum_standalone

**Category:** clarity
**Description:** Summary is self-contained — no context needed to understand it

**Pass Condition:** Doesn't reference 'the post' or 'the author'. Defines any jargon. A reader with no context gets the point.

**Scoring Method:** `penalty_based`
**Max Points:** 6

### Penalties

- **references_source:** -2.0 pts
- **undefined_jargon:** -1.5 pts
- **assumes_context:** -1.5 pts
- **passive_voice_dominant:** -1.0 pts

### Pass Examples

- Self-contained claims that work as standalone intelligence

### Fail Examples

- 'The author argues that...' or 'This post explores...'

---
