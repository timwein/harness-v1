# Rubric: business_strategy

**Task:** Create a procurement negotiation playbook for a $500K enterprise SaaS deal, including BATNA analysis, concession strategy, anchoring tactics, and scripted responses to 5 common vendor objections

**Domain:** business_strategy
**Total Points:** 52
**Pass Threshold:** 85%
**Criteria Count:** 5
**Generated:** 2026-03-31 05:57:57 UTC

---

## 1. neg_batna

**Category:** strategy
**Description:** BATNA analysis is thorough and quantified, not just 'we could walk away'

**Pass Condition:** Identifies 2-3 specific alternatives with cost/capability comparison. Quantifies switching costs. Defines reservation price and ZOPA. Assesses vendor's BATNA as well.

**Scoring Method:** `weighted_components`
**Max Points:** 14

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `alternative_depth` | 30% | 2-3 specific named alternatives with cost estimates | 1.0 if 2-3 quantified alternatives, 0.5 if vague alternatives, 0.0 if just 'walk away' |
| `switching_cost` | 25% | Quantifies migration/switching costs for each alternative | 1.0 if $ estimates for switching, 0.5 if qualitative, 0.0 if not addressed |
| `reservation_price` | 20% | Clear reservation price derived from BATNA analysis | 1.0 if derived from analysis, 0.5 if stated without derivation, 0.0 if absent |
| `vendor_batna` | 25% | Estimates the vendor's BATNA and leverage | 1.0 if vendor's alternatives assessed, 0.5 if mentioned, 0.0 if one-sided |

### Pass Examples

- BATNA: (1) Competitor X at $420K but needs $80K migration; (2) Build in-house at $350K first-year but $200K/yr maintenance; Reservation price: $480K

### Fail Examples

- 'If they don't give us a good price, we'll go with someone else'

---

## 2. neg_concession_strategy

**Category:** tactics
**Description:** Concession strategy is structured, not improvised — with clear give/get trades

**Pass Condition:** Ranked list of concessions with estimated value to each side. Linked trades (give X, get Y). Never concede without getting something back. Starts with high-value-to-them, low-cost-to-us concessions.

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `concession_ranking` | 30% | Concessions ranked by value and cost | 1.0 if ranked matrix of give/get with values, 0.5 if list, 0.0 if ad hoc |
| `linked_trades` | 30% | Each concession is linked to a reciprocal ask | % of concessions with explicit linked gets |
| `value_asymmetry` | 25% | Identifies concessions cheap for us but valuable to vendor | 1.0 if asymmetric value analysis, 0.5 if basic, 0.0 if not analyzed |
| `sequencing` | 15% | Clear order of concessions from least to most costly | 1.0 if sequenced, 0.0 if unordered |

### Pass Examples

- Concession 1: Agree to 3-year term (low cost to us, high value to vendor for ARR predictability) → Get: 20% volume discount + quarterly billing

### Fail Examples

- 'We can offer a longer contract if needed'

---

## 3. neg_objection_scripts

**Category:** execution
**Description:** Scripted responses to 5 vendor objections are realistic and effective

**Pass Condition:** 5 common objections (price is firm, feature not available, competitor comparison, implementation timeline, contract terms). Each has: verbatim vendor line, why they say it, and 2-3 response options with different assertiveness levels.

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `objection_realism` | 30% | Objections are things vendors actually say in enterprise deals | % of objections that are realistic vendor positions |
| `response_quality` | 35% | Responses address the underlying interest, not just the position | % of responses that reframe using interest-based negotiation |
| `response_options` | 20% | Multiple response options per objection (soft/medium/firm) | 1.0 if 2-3 options per objection, 0.5 if single response, 0.0 if no scripts |
| `tactical_depth` | 15% | Responses use specific negotiation techniques (labeling, mirroring, anchoring) | 1.0 if named techniques, 0.5 if implicit, 0.0 if generic |

### Pass Examples

- Objection: 'Our pricing is non-negotiable at this tier.' Response (medium): 'I understand the list price reflects your standard packaging. We're committed to your platform — what if we structured this as a 3-year agreement? That gives your team ARR predictability, and we'd need the economics to reflect that commitment.'

### Fail Examples

- 'If they say the price is firm, tell them we need a discount'

---

## 4. neg_anchoring

**Category:** tactics
**Description:** Anchoring strategy is specific with first-offer rationale and counteroffer preparation

**Pass Condition:** Defines first offer with justification (benchmark, competitor pricing, ROI analysis). Prepares for vendor's anchor with re-anchoring tactics. Uses objective criteria to support anchor.

**Scoring Method:** `weighted_components`
**Max Points:** 8

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `first_offer` | 40% | Specific first offer with data-backed justification | 1.0 if $ amount with rationale, 0.5 if vague range, 0.0 if no anchor |
| `counter_anchor` | 30% | Prepared response to vendor's opening anchor | 1.0 if re-anchoring strategy, 0.5 if basic counter, 0.0 if unprepared |
| `objective_criteria` | 30% | Anchored in market data, ROI, or benchmarks | 1.0 if data-backed, 0.5 if qualitative, 0.0 if arbitrary |

### Pass Examples

- First offer: $375K (25% below list) anchored on: (1) G2 benchmark data showing 30% avg enterprise discount, (2) Competitor X quoted $400K for similar scope

### Fail Examples

- 'Start low and negotiate up'

---

## 5. neg_structure

**Category:** usability
**Description:** Playbook is structured for use during actual negotiation, not just pre-read

**Pass Condition:** Quick-reference format. Decision tree for common scenarios. Red lines clearly marked. Escalation criteria defined. Summary card for negotiator to bring to the meeting.

**Scoring Method:** `weighted_components`
**Max Points:** 6

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `quick_reference` | 35% | Summary card or cheat sheet for live use | 1.0 if one-page reference card, 0.5 if summary section, 0.0 if long-form only |
| `decision_tree` | 30% | If/then logic for common negotiation branches | 1.0 if decision tree or flowchart, 0.5 if scenarios listed, 0.0 if linear |
| `red_lines` | 35% | Non-negotiable terms clearly marked | 1.0 if red lines explicit, 0.0 if no boundaries defined |

### Pass Examples

- ## Red Lines (Do Not Cross)
- No auto-renewal without 90-day notice clause
- No unlimited liability for our data breach
## Quick Reference Card
...

### Fail Examples

- 10-page essay with no reference format for live use

---
