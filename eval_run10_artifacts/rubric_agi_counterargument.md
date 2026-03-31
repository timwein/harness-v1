# Rubric: argumentation

**Task:** Write a counterargument to the claim 'AGI will arrive before 2030'

**Domain:** argumentation
**Total Points:** 36
**Pass Threshold:** 80%
**Criteria Count:** 4
**Generated:** 2026-03-31 05:56:46 UTC

---

## 1. arg_steelman

**Category:** intellectual_honesty
**Description:** Steelmans the original claim before countering it

**Pass Condition:** First paragraph presents the strongest version of the AGI-by-2030 case. Cites real scaling results, benchmarks, expert proponents. Shows the reader you understand why smart people believe this.

**Scoring Method:** `weighted_components`
**Max Points:** 10

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `steelman_quality` | 50% | Presents strongest version of the claim | 1.0 if cites specific results/proponents, 0.5 if generic, 0.0 if strawman |
| `specific_evidence` | 30% | References real benchmarks, papers, or expert positions | 1.0 if 2+ specific references, 0.5 if 1, 0.0 if none |
| `good_faith` | 20% | Reader feels the argument was fairly represented | 1.0 if fair, 0.0 if dismissive/strawman |

### Pass Examples

- 'The case for AGI by 2030 is stronger than critics admit: GPT-4 to o3 showed...'

### Fail Examples

- 'Some people naively believe AGI is coming soon, but...'

---

## 2. arg_counter_quality

**Category:** argumentation
**Description:** Counterarguments are specific, non-obvious, and empirically grounded

**Pass Condition:** 3+ distinct counter-threads. At least one challenges the definition of AGI. At least one is empirical (benchmarking issues, capability gaps). At least one is structural (alignment, deployment, regulation).

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `argument_count` | 20% | 3+ distinct counter-threads | 1.0 if 3+, 0.5 if 2, 0.0 if 1 |
| `definitional_challenge` | 25% | Challenges what 'AGI' means and why it matters | 1.0 if substantive definitional argument, 0.0 if skips it |
| `empirical_grounding` | 30% | Cites specific capability gaps, benchmark limitations | 1.0 if specific gaps with evidence, 0.5 if general, 0.0 if hand-wavy |
| `structural_barriers` | 25% | Addresses alignment, regulation, deployment realities | 1.0 if specific structural argument, 0.5 if mentioned, 0.0 if absent |

### Pass Examples

- Definitional ambiguity + benchmark saturation without real-world transfer + regulatory friction

### Fail Examples

- 'AI is overhyped' repeated three different ways

---

## 3. arg_nuance

**Category:** sophistication
**Description:** Avoids absolutism — acknowledges uncertainty and conditions

**Pass Condition:** Uses probabilistic language. Identifies conditions under which the claim could be true. Distinguishes 'narrow AGI' from 'transformative AI'. Doesn't claim to know the answer.

**Scoring Method:** `penalty_based`
**Max Points:** 8

### Penalties

- **absolutist_claim:** -2.5 pts
- **dismisses_without_evidence:** -2.0 pts
- **ignores_counterexamples:** -1.5 pts
- **no_uncertainty_acknowledgment:** -2.0 pts
- **appeal_to_authority_only:** -1.0 pts

### Pass Examples

- 'AGI by 2030 is possible but improbable — here's why the base rate for such predictions is poor'

### Fail Examples

- 'AGI will definitely not happen by 2030'

---

## 4. arg_readability

**Category:** communication
**Description:** Well-structured, scannable, persuasive prose

**Pass Condition:** Clear thesis in first paragraph. Each counter-thread in its own section. Conclusion synthesizes. Under 800 words.

**Scoring Method:** `weighted_components`
**Max Points:** 6

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `structure` | 40% | Thesis → steelman → counters → synthesis | 1.0 if clear structure, 0.5 if partially organized, 0.0 if stream of consciousness |
| `concision` | 30% | Under 800 words, no padding | 1.0 if ≤800, 0.7 if ≤1000, 0.0 if >1200 |
| `persuasive_flow` | 30% | Builds momentum, ends strong | 1.0 if compelling arc, 0.5 if flat, 0.0 if scattered |

### Pass Examples

- 700 words, clear sections, ends with a memorable reframe

### Fail Examples

- 1500-word stream of consciousness with no structure

---
