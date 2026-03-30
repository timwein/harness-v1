# Attention Explanation — Rubric

**Task:** Explain transformer attention mechanisms to a smart 16-year-old
**Domain:** explanation
**Total Points:** 36
**Pass Threshold:** 80%

---

## expl_accuracy

**Category:** correctness

**Description:** Technical content is correct — no simplification-induced errors

**Pass Condition:** Query/Key/Value framework explained correctly. Dot product similarity is accurate. Softmax described correctly. Multi-head attention's purpose is right.

**Scoring Method:** WEIGHTED_COMPONENTS (max 12 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| qkv_correctness | Q/K/V roles explained accurately | 0.35 | 1.0 if correct mechanism, 0.5 if metaphor-only, 0.0 if wrong |
| attention_math | Dot product + softmax pipeline correct | 0.35 | 1.0 if mechanism right, 0.5 if hand-wavy but directionally correct, 0.0 if wrong |
| multihead_purpose | Why multiple heads matter | 0.30 | 1.0 if explains different relationship types, 0.5 if mentions it, 0.0 if absent |

**Pass Examples:** "Each word asks a question (query), advertises what it knows (key), and shares details (value)"

**Fail Examples:** "Attention is when the model focuses on important words" — no mechanism

---

## expl_accessibility

**Category:** audience_fit

**Description:** A smart 16-year-old actually understands it after reading

**Pass Condition:** No unexplained jargon. Uses analogies from their world. Builds from familiar concepts (search, recommendation) to new ones. Math level: algebra ok, linear algebra explained if used.

**Scoring Method:** WEIGHTED_COMPONENTS (max 10 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| jargon_handling | All technical terms explained or avoided | 0.30 | 1.0 if all explained, 0.5 if most, 0.0 if jargon-heavy |
| analogy_quality | Uses relatable analogies (social media, school, etc.) | 0.35 | 1.0 if memorable analogy that maps correctly, 0.5 if generic, 0.0 if none |
| progressive_complexity | Builds from simple to complex | 0.35 | 1.0 if clear scaffold, 0.5 if some structure, 0.0 if jumps to hard parts |

**Pass Examples:** Starts with "imagine searching for a video on YouTube" → builds to Q/K/V

**Fail Examples:** "Attention computes softmax(QK^T/√d_k)V" with no unpacking

---

## expl_engagement

**Category:** communication

**Description:** Explanation is engaging — a 16-year-old would actually read to the end

**Pass Condition:** Conversational tone. Not condescending. Includes a 'whoa' moment. Under 600 words. Has a hook in the first sentence.

**Scoring Method:** WEIGHTED_COMPONENTS (max 8 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| hook | First sentence creates curiosity | 0.30 | 1.0 if compelling hook, 0.5 if adequate, 0.0 if textbook opening |
| tone | Conversational, not textbook or condescending | 0.35 | 1.0 if natural, 0.5 if slightly formal, 0.0 if textbook/patronizing |
| concision | Under 600 words, no padding | 0.35 | 1.0 if ≤600, 0.7 if ≤800, 0.0 if >1000 |

**Pass Examples:** "You know how autocomplete seems to read your mind? Here's the trick..."

**Fail Examples:** "Attention mechanisms are a fundamental component of transformer architectures..."

---

## expl_completeness

**Category:** coverage

**Description:** Covers the essential pieces without going too deep

**Pass Condition:** Covers: why attention exists (context problem), how it works (Q/K/V), why it matters (parallel processing, long-range dependencies). Doesn't require covering positional encoding, layer norm, etc.

**Scoring Method:** WEIGHTED_COMPONENTS (max 6 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| motivation | Explains why attention was invented (the problem it solves) | 0.35 | 1.0 if clear problem statement, 0.5 if implied, 0.0 if jumps to mechanism |
| mechanism | How attention works at an intuitive level | 0.35 | 1.0 if clear mechanism, 0.0 if vague |
| significance | Why it matters / what it enabled | 0.30 | 1.0 if connects to real impact, 0.5 if mentioned, 0.0 if absent |

**Pass Examples:** Problem (RNNs forget) → Mechanism (Q/K/V attention) → Impact (ChatGPT, translation)

**Fail Examples:** Deep dive into multi-head attention math with no motivation
