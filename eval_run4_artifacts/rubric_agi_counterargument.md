# AGI Counterargument — Rubric

**Task:** Write a counterargument to the claim 'AGI will arrive before 2030'
**Domain:** argumentation
**Total Points:** 36
**Pass Threshold:** 80%

---

## arg_steelman

**Category:** intellectual_honesty

**Description:** Steelmans the original claim before countering it

**Pass Condition:** First paragraph presents the strongest version of the AGI-by-2030 case. Cites real scaling results, benchmarks, expert proponents. Shows the reader you understand why smart people believe this.

**Scoring Method:** WEIGHTED_COMPONENTS (max 10 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| steelman_quality | Presents strongest version of the claim | 0.50 | 1.0 if cites specific results/proponents, 0.5 if generic, 0.0 if strawman |
| specific_evidence | References real benchmarks, papers, or expert positions | 0.30 | 1.0 if 2+ specific references, 0.5 if 1, 0.0 if none |
| good_faith | Reader feels the argument was fairly represented | 0.20 | 1.0 if fair, 0.0 if dismissive/strawman |

**Pass Examples:** "The case for AGI by 2030 is stronger than critics admit: GPT-4 to o3 showed..."

**Fail Examples:** "Some people naively believe AGI is coming soon, but..."

---

## arg_counter_quality

**Category:** argumentation

**Description:** Counterarguments are specific, non-obvious, and empirically grounded

**Pass Condition:** 3+ distinct counter-threads. At least one challenges the definition of AGI. At least one is empirical (benchmarking issues, capability gaps). At least one is structural (alignment, deployment, regulation).

**Scoring Method:** WEIGHTED_COMPONENTS (max 12 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| argument_count | 3+ distinct counter-threads | 0.20 | 1.0 if 3+, 0.5 if 2, 0.0 if 1 |
| definitional_challenge | Challenges what 'AGI' means and why it matters | 0.25 | 1.0 if substantive definitional argument, 0.0 if skips it |
| empirical_grounding | Cites specific capability gaps, benchmark limitations | 0.30 | 1.0 if specific gaps with evidence, 0.5 if general, 0.0 if hand-wavy |
| structural_barriers | Addresses alignment, regulation, deployment realities | 0.25 | 1.0 if specific structural argument, 0.5 if mentioned, 0.0 if absent |

**Pass Examples:** Definitional ambiguity + benchmark saturation without real-world transfer + regulatory friction

**Fail Examples:** "AI is overhyped" repeated three different ways

---

## arg_nuance

**Category:** sophistication

**Description:** Avoids absolutism — acknowledges uncertainty and conditions

**Pass Condition:** Uses probabilistic language. Identifies conditions under which the claim could be true. Distinguishes 'narrow AGI' from 'transformative AI'. Doesn't claim to know the answer.

**Scoring Method:** PENALTY_BASED (max 8 pts)

| Penalty | Points Deducted |
|---|---|
| absolutist_claim | -2.5 |
| dismisses_without_evidence | -2.0 |
| ignores_counterexamples | -1.5 |
| no_uncertainty_acknowledgment | -2.0 |
| appeal_to_authority_only | -1.0 |

**Pass Examples:** "AGI by 2030 is possible but improbable — here's why the base rate for such predictions is poor"

**Fail Examples:** "AGI will definitely not happen by 2030"

---

## arg_readability

**Category:** communication

**Description:** Well-structured, scannable, persuasive prose

**Pass Condition:** Clear thesis in first paragraph. Each counter-thread in its own section. Conclusion synthesizes. Under 800 words.

**Scoring Method:** WEIGHTED_COMPONENTS (max 6 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| structure | Thesis → steelman → counters → synthesis | 0.40 | 1.0 if clear structure, 0.5 if partially organized, 0.0 if stream of consciousness |
| concision | Under 800 words, no padding | 0.30 | 1.0 if ≤800, 0.7 if ≤1000, 0.0 if >1200 |
| persuasive_flow | Builds momentum, ends strong | 0.30 | 1.0 if compelling arc, 0.5 if flat, 0.0 if scattered |

**Pass Examples:** 700 words, clear sections, ends with a memorable reframe

**Fail Examples:** 1500-word stream of consciousness with no structure
