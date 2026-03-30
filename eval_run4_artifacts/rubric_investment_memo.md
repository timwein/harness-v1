# Investment Memo — Rubric

**Task:** Draft a 1-page investment memo on a hypothetical Series A company in the defense drone space
**Domain:** investment_memo
**Total Points:** 44
**Pass Threshold:** 85%

---

## memo_structure

**Category:** format

**Description:** Follows standard 1-page memo format with all required sections

**Pass Condition:** Sections: Company Overview, Market Opportunity, Product/Technology, Team, Traction, Deal Terms, Key Risks, Recommendation. Fits on one page (~500-700 words).

**Scoring Method:** WEIGHTED_COMPONENTS (max 10 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| section_coverage | All required sections present | 0.35 | % of required sections (overview, market, product, team, traction, terms, risks, rec) |
| page_constraint | Fits on one page (500-700 words) | 0.30 | 1.0 if 500-700 words, 0.7 if 700-850, 0.3 if 400-500, 0.0 if >900 |
| scannable_format | Headers, bullets within sections, dense but readable | 0.35 | 1.0 if scannable with clear visual hierarchy, 0.0 if wall of text |

**Pass Examples:** 8 sections, 650 words, each section 2-4 bullet points

**Fail Examples:** 3-page narrative essay, or 200-word skim

---

## memo_market

**Category:** analysis

**Description:** Market opportunity is sized and specific to defense drones, not generic TAM

**Pass Condition:** SAM/SOM, not just TAM. Specific to defense drone segment. Cites or constructs credible numbers. Identifies tailwinds (DoD budget trends, Ukraine lessons, NDAA provisions).

**Scoring Method:** WEIGHTED_COMPONENTS (max 10 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| market_specificity | Defense drone SAM, not generic 'drone market' | 0.35 | 1.0 if defense-specific SAM/SOM, 0.5 if TAM only, 0.0 if generic |
| credible_sizing | Numbers are plausible with cited or constructed basis | 0.30 | 1.0 if sourced/constructed, 0.5 if asserted, 0.0 if absent |
| tailwind_identification | Specific policy/geopolitical tailwinds cited | 0.35 | % of relevant tailwinds identified (DoD budget, NDAA, Ukraine, Replicator) |

**Pass Examples:** "Defense sUAS SAM: $8B by 2028 (up from $3B), driven by DoD Replicator initiative and FY26 NDAA line items"

**Fail Examples:** "The global drone market is expected to reach $50B by 2030"

---

## memo_thesis

**Category:** conviction

**Description:** Investment thesis is crisp — clear 'why this company, why now'

**Pass Condition:** 2-3 sentence thesis that answers: What's the insight? Why is this team positioned? What's the timing catalyst? Must be specific enough that it couldn't apply to any defense startup.

**Scoring Method:** WEIGHTED_COMPONENTS (max 10 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| insight_clarity | Core insight is specific and non-obvious | 0.40 | 1.0 if specific insight, 0.5 if generic but directionally right, 0.0 if boilerplate |
| team_match | Why this team specifically is positioned to win | 0.30 | 1.0 if specific team-market fit, 0.5 if generic team praise, 0.0 if absent |
| timing_catalyst | Clear 'why now' with specific catalyst | 0.30 | 1.0 if specific timing argument, 0.5 if vague, 0.0 if absent |

**Pass Examples:** "DoD is shifting from $50M primes-built systems to $500K attritable drones — [Company] has the only NDAA-compliant autonomy stack that integrates with existing C2 systems, built by ex-Anduril engineers who shipped the first production Altius system."

**Fail Examples:** "Defense is a big market and drones are the future."

---

## memo_risks

**Category:** diligence

**Description:** Key risks are honest, specific, and include mitigants

**Pass Condition:** 3-5 real risks (not strawmen). At least one each: market risk, execution risk, regulatory/ITAR risk. Each has a mitigant or monitoring plan.

**Scoring Method:** WEIGHTED_COMPONENTS (max 8 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| risk_quality | Risks are real and specific, not generic | 0.40 | % of risks that are specific to this company/market |
| risk_coverage | Market, execution, and regulatory/ITAR risks all addressed | 0.30 | 1.0 if all 3 categories, 0.5 if 2, 0.0 if 1 |
| mitigants | Each risk has a plausible mitigant or monitoring plan | 0.30 | % of risks with stated mitigants |

**Pass Examples:** "ITAR compliance burden limits sales velocity — mitigant: CTO has existing DSP-5/DSP-73 experience from Lockheed tenure"

**Fail Examples:** "Risk: competition. Risk: market might not grow."

---

## memo_deal_terms

**Category:** practicality

**Description:** Deal terms are realistic and internally consistent

**Pass Condition:** Pre-money valuation, round size, lead investor type, and use of funds. Values are stage-appropriate (Series A defense: $15-40M pre). Use of funds is specific (hiring, ITAR facility, production line).

**Scoring Method:** WEIGHTED_COMPONENTS (max 6 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| completeness | Valuation, round size, ownership target stated | 0.40 | % of deal terms present |
| stage_appropriateness | Values are realistic for Series A defense startup | 0.30 | 1.0 if realistic, 0.5 if slightly off, 0.0 if unrealistic |
| use_of_funds | Specific allocation of capital | 0.30 | 1.0 if specific breakdown, 0.5 if vague, 0.0 if absent |

**Pass Examples:** "$20M Series A at $60M pre. Use: 40% eng/autonomy, 25% ITAR facility, 20% BD, 15% ops"

**Fail Examples:** "Raising a Series A at a good valuation"
