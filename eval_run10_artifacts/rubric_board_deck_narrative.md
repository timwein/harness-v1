# Rubric: business_communication

**Task:** Write the narrative script (speaker notes) for a 12-slide Series B board deck covering financials, product roadmap, competitive landscape, hiring plan, and key risks, for a $30M ARR vertical SaaS company

**Domain:** business_communication
**Total Points:** 52
**Pass Threshold:** 85%
**Criteria Count:** 5
**Generated:** 2026-03-31 05:57:56 UTC

---

## 1. bd_structure

**Category:** organization
**Description:** 12 slides with clear narrative arc from performance → strategy → risks

**Pass Condition:** Exactly 12 slides. Logical sequence: title, metrics/financials, product, market/competitive, go-to-market, hiring, risks, ask/next steps. Each slide has 3-5 sentences of speaker notes.

**Scoring Method:** `weighted_components`
**Max Points:** 10

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `slide_count` | 25% | Exactly 12 slides with distinct topics | 1.0 if 12, 0.7 if 10-11, 0.5 if 8-9, 0.0 if <8 |
| `narrative_arc` | 40% | Logical flow: performance → opportunity → plan → risks → ask | 1.0 if clear arc, 0.5 if sections present but poorly ordered, 0.0 if random |
| `notes_density` | 35% | Speaker notes are 3-5 sentences per slide, not too thin or bloated | % of slides with appropriate density (3-5 sentences) |

### Pass Examples

- Slide 1: Title/Agenda → Slide 2: KPI Dashboard → ... → Slide 11: Key Risks → Slide 12: Board Ask

### Fail Examples

- 8 slides, no risk section, speaker notes that are full paragraphs

---

## 2. bd_financial_literacy

**Category:** content
**Description:** Financial content reflects Series B SaaS literacy — correct metrics and benchmarks

**Pass Condition:** Includes ARR, growth rate, NDR, gross margin, burn rate, runway, CAC/LTV, payback period. Numbers are internally consistent and plausible for $30M ARR. References relevant benchmarks (Bessemer, KeyBanc).

**Scoring Method:** `weighted_components`
**Max Points:** 14

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `metric_coverage` | 30% | All key SaaS metrics present (ARR, NDR, GM, burn, CAC/LTV) | % of required metrics covered |
| `internal_consistency` | 35% | Numbers don't contradict each other (e.g., burn vs runway vs headcount) | 1.0 if all consistent, 0.5 if minor inconsistencies, 0.0 if contradictions |
| `benchmark_awareness` | 35% | References industry benchmarks for $30M ARR stage | 1.0 if benchmarked against relevant data, 0.5 if generic, 0.0 if no context |

### Pass Examples

- $30M ARR, 85% YoY growth (T2D3 pace), 125% NDR, 78% gross margin, 18-month runway at current burn of $2.5M/mo

### Fail Examples

- $30M ARR with 95% gross margin, 200% NDR, and infinite runway — internally inconsistent

---

## 3. bd_competitive_depth

**Category:** analysis
**Description:** Competitive landscape shows genuine strategic thinking, not just a feature matrix

**Pass Condition:** Identifies 3-5 competitors with honest positioning. Explains differentiation in terms of market segments, not features. Addresses where competitors are winning and company's strategic response.

**Scoring Method:** `weighted_components`
**Max Points:** 10

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `competitor_depth` | 35% | 3-5 competitors analyzed with real strategic insight | 1.0 if 3-5 with genuine analysis, 0.5 if surface-level, 0.0 if just names |
| `honest_positioning` | 35% | Acknowledges where competitors are strong, not just FUD | 1.0 if balanced, 0.5 if mostly self-serving, 0.0 if only weaknesses of others |
| `strategic_response` | 30% | Clear strategic response to competitive threats | 1.0 if specific moat/response per threat, 0.5 if generic, 0.0 if absent |

### Pass Examples

- 'Competitor X dominates mid-market with a self-serve motion. Our response: we win on enterprise where workflow complexity makes their generic tool insufficient.'

### Fail Examples

- Feature comparison table showing we win every category

---

## 4. bd_risk_candor

**Category:** judgment
**Description:** Risk section is candid about real threats, not softball risks

**Pass Condition:** At least 4 genuine risks. Includes both execution risks and market risks. Each risk has a mitigation plan. Doesn't list only risks you've already solved.

**Scoring Method:** `weighted_components`
**Max Points:** 10

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `risk_authenticity` | 40% | Risks are genuine threats a board member would worry about | 1.0 if board-level risks, 0.5 if mid-management concerns, 0.0 if softballs |
| `risk_diversity` | 30% | Mix of execution, market, competitive, and team risks | 1.0 if 3+ risk categories, 0.5 if 2, 0.0 if all same type |
| `mitigation_specificity` | 30% | Each risk has a specific mitigation, not 'we're monitoring this' | % of risks with actionable mitigation plans |

### Pass Examples

- 'Risk: Key competitor raised $100M and is underpricing by 40% in our core segment. Mitigation: Accelerating product-led growth for SMB while doubling down on enterprise where price sensitivity is lower.'

### Fail Examples

- 'Risk: the economy might slow down. Mitigation: we'll keep an eye on it.'

---

## 5. bd_audience_calibration

**Category:** tone
**Description:** Tone and depth are calibrated for a board audience — strategic, not operational

**Pass Condition:** CEO-level framing, not manager-level detail. Strategic choices explained, not task lists. Data-backed assertions. Confident but not dismissive of challenges.

**Scoring Method:** `penalty_based`
**Max Points:** 8

### Penalties

- **too_operational:** -2.0 pts
- **no_data_backing:** -2.0 pts
- **defensive_tone:** -1.5 pts
- **jargon_without_context:** -1.5 pts
- **sycophantic_to_board:** -1.5 pts
- **too_long_per_slide:** -1.0 pts

### Pass Examples

- 'We chose to invest in enterprise over SMB this quarter because NDR is 140% vs 105%, and the CAC payback is 8 months vs 14.'

### Fail Examples

- 'The team has been working really hard on a lot of great features this quarter'

---
