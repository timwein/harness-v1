# Rubric: legal_analysis

**Task:** Redline a cloud services SaaS agreement from the customer's perspective, identifying 10 risky clauses and proposing specific alternative language with justification for each

**Domain:** legal_analysis
**Total Points:** 46
**Pass Threshold:** 85%
**Criteria Count:** 4
**Generated:** 2026-03-31 05:57:10 UTC

---

## 1. legal_clause_identification

**Category:** analysis
**Description:** Identifies genuinely risky clauses that matter to enterprise customers

**Pass Condition:** 10 distinct clauses identified. Covers: liability caps, indemnification, data ownership, termination, SLA, IP assignment, audit rights, data portability, governing law, and auto-renewal. Each risk is specific, not generic.

**Scoring Method:** `weighted_components`
**Max Points:** 14

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `clause_count` | 20% | Exactly 10 distinct risky clauses identified | 1.0 if 10, 0.7 if 8-9, 0.5 if 6-7, 0.0 if <6 |
| `risk_diversity` | 35% | Covers multiple risk categories (commercial, legal, technical, operational) | 1.0 if 4+ categories, 0.5 if 2-3, 0.0 if all same type |
| `risk_specificity` | 45% | Each risk is specific to the clause language, not generic boilerplate advice | % of clauses with specific risk tied to actual contract language patterns |

### Pass Examples

- 'Clause 7.2 caps vendor liability at 12 months of fees — this is standard but should be uncapped for data breaches and IP infringement'

### Fail Examples

- 'The contract has risky terms' or listing generic legal concepts without clause references

---

## 2. legal_alternative_language

**Category:** drafting
**Description:** Proposed alternative language is legally precise and practically negotiable

**Pass Condition:** Each of the 10 clauses has specific replacement language (not just 'change this'). Language is contract-grade (not casual prose). Alternatives are commercially reasonable, not one-sided wishlists.

**Scoring Method:** `weighted_components`
**Max Points:** 14

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `specificity` | 35% | Actual replacement clause text, not just 'negotiate better terms' | % of clauses with word-for-word replacement language |
| `legal_precision` | 30% | Language uses proper legal drafting conventions | 1.0 if contract-grade language, 0.5 if close, 0.0 if casual prose |
| `commercial_reasonableness` | 35% | Proposals a vendor would actually consider, not maximalist demands | % of proposals that are commercially balanced rather than one-sided |

### Pass Examples

- 'Replace: "Vendor's total liability shall not exceed fees paid in the preceding 12 months" With: "...shall not exceed 2x fees paid in the preceding 12 months, provided that this cap shall not apply to (i) breaches of Section X (Data Protection), (ii) indemnification obligations under Section Y..."'

### Fail Examples

- 'Negotiate a higher liability cap' or 'Remove this clause entirely'

---

## 3. legal_justification

**Category:** reasoning
**Description:** Each redline includes business and legal justification, not just risk flagging

**Pass Condition:** Each clause has: what the risk is, why it matters to the customer specifically, what the market-standard position is, and what leverage the customer has.

**Scoring Method:** `weighted_components`
**Max Points:** 10

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `risk_explanation` | 35% | Explains WHY the clause is risky, not just THAT it is | % of clauses with specific risk scenario (not just 'this is risky') |
| `market_context` | 35% | References market-standard positions or benchmarks | % of clauses with market-standard comparison |
| `negotiation_leverage` | 30% | Notes where customer has leverage and where to concede | 1.0 if prioritizes fights, 0.5 if treats all equally, 0.0 if no strategy |

### Pass Examples

- 'Uncapped liability for data breaches is market-standard in enterprise SaaS (cf. SOC 2 expectations). This is a high-leverage ask because...'

### Fail Examples

- 'This clause is unfavorable to the customer'

---

## 4. legal_organization

**Category:** structure
**Description:** Redline is organized by priority with clear formatting for legal review

**Pass Condition:** Organized by priority (critical → important → nice-to-have). Consistent format: clause reference, original text, proposed text, justification. Executive summary at top.

**Scoring Method:** `weighted_components`
**Max Points:** 8

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `prioritization` | 35% | Clauses ordered by risk severity with priority labels | 1.0 if tiered (critical/important/nice-to-have), 0.5 if ordered but unlabeled, 0.0 if random |
| `consistent_format` | 35% | Each redline follows same structure | 1.0 if all 10 follow identical format, 0.5 if mostly, 0.0 if inconsistent |
| `executive_summary` | 30% | Top-level summary of key risks and negotiation strategy | 1.0 if summary present, 0.0 if dives straight into clauses |

### Pass Examples

- ## Executive Summary
3 critical, 4 important, 3 nice-to-have redlines...

### Critical 1: Liability Cap (Section 7.2)
**Current:** ... **Proposed:** ... **Justification:** ...

### Fail Examples

- Unstructured list of complaints about the contract

---
