# Rubric: strategic_analysis

**Task:** Write a competitive analysis memo comparing 4 AI code assistant tools (Cursor, GitHub Copilot, Cody, Windsurf) across 8 dimensions with a recommendation for a 200-person engineering org

**Domain:** strategic_analysis
**Total Points:** 52
**Pass Threshold:** 85%
**Criteria Count:** 5
**Generated:** 2026-03-31 05:57:16 UTC

---

## 1. ca_framework

**Category:** structure
**Description:** Analysis framework has 8 clearly defined dimensions with consistent evaluation

**Pass Condition:** 8 distinct evaluation dimensions covering: code quality, IDE integration, language support, privacy/security, pricing, team features, context understanding, and customization. Each dimension applied consistently across all 4 tools.

**Scoring Method:** `weighted_components`
**Max Points:** 10

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `dimension_count` | 25% | Exactly 8 distinct, non-overlapping dimensions | 1.0 if 8 distinct, 0.7 if 6-7, 0.5 if 4-5, 0.0 if <4 |
| `dimension_quality` | 35% | Dimensions are decision-relevant for a 200-person org | % of dimensions that matter at enterprise scale (security, admin, cost) |
| `consistent_application` | 40% | Each dimension evaluated for all 4 tools | 1.0 if complete 4x8 matrix, 0.5 if gaps, 0.0 if inconsistent |

### Pass Examples

- Dimensions: (1) Code generation accuracy, (2) Context window utilization, (3) IDE ecosystem, (4) Security/privacy, (5) Pricing at scale, (6) Admin/governance, (7) Customization, (8) Roadmap/trajectory

### Fail Examples

- 3 vague categories like 'Features', 'Price', 'Quality'

---

## 2. ca_accuracy

**Category:** content
**Description:** Factual claims about products are accurate and current

**Pass Condition:** Pricing, features, and limitations are factually correct for current versions. Distinguishes between GA features and beta/preview. No outdated information. Sources or basis for claims stated.

**Scoring Method:** `weighted_components`
**Max Points:** 14

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `factual_accuracy` | 40% | Claims about each tool are verifiably correct | % of factual claims that are accurate |
| `currency` | 30% | Information reflects current product state, not 6-month-old features | 1.0 if current, 0.5 if mostly current, 0.0 if outdated |
| `ga_vs_beta` | 30% | Distinguishes GA features from beta/preview/announced | 1.0 if clearly distinguished, 0.5 if sometimes, 0.0 if no distinction |

### Pass Examples

- 'Cursor Pro: $20/user/mo with 500 fast requests (GPT-4/Claude), unlimited slow requests. Business: $40/user/mo with admin controls, SSO.'

### Fail Examples

- Outdated pricing or features that were announced but never shipped

---

## 3. ca_recommendation

**Category:** judgment
**Description:** Recommendation is defensible, acknowledges tradeoffs, and fits the stated context

**Pass Condition:** Clear primary recommendation with rationale. Addresses why not the alternatives. Considers the 200-person org context (security, admin, cost at scale). Suggests evaluation/pilot approach.

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `clear_recommendation` | 30% | Unambiguous primary pick with specific rationale | 1.0 if clear pick with reasoning, 0.5 if hedged, 0.0 if 'it depends' |
| `tradeoff_honesty` | 30% | Acknowledges what you give up with the recommendation | 1.0 if explicit tradeoffs, 0.5 if mentioned, 0.0 if only positives |
| `context_fit` | 20% | Recommendation specifically addresses 200-person enterprise needs | 1.0 if enterprise-specific (SSO, admin, compliance), 0.5 if generic, 0.0 if individual-focused |
| `rollout_plan` | 20% | Suggests phased evaluation or pilot approach | 1.0 if phased rollout plan, 0.5 if basic suggestion, 0.0 if no rollout guidance |

### Pass Examples

- 'Recommend Cursor Business for primary adoption with a 30-day pilot across 3 teams. Key tradeoff: higher per-seat cost vs Copilot, justified by superior context understanding and agent capabilities.'

### Fail Examples

- 'All tools have pros and cons, so it depends on your needs'

---

## 4. ca_depth

**Category:** analysis
**Description:** Analysis goes beyond feature lists to strategic and workflow implications

**Pass Condition:** Covers workflow impact (not just features), team dynamics, vendor risk, and trajectory/roadmap considerations. Includes at least 2 second-order insights that wouldn't be obvious from product pages.

**Scoring Method:** `weighted_components`
**Max Points:** 10

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `beyond_features` | 35% | Discusses workflow impact, productivity gains, learning curve | 1.0 if workflow analysis, 0.5 if feature-focused, 0.0 if just feature list |
| `vendor_risk` | 30% | Considers vendor viability, lock-in, and strategic direction | 1.0 if vendor risk assessed, 0.5 if mentioned, 0.0 if absent |
| `second_order_insights` | 35% | At least 2 non-obvious insights (e.g., impact on code review culture) | 1.0 if 2+ genuine insights, 0.5 if 1, 0.0 if all obvious |

### Pass Examples

- 'Second-order effect: teams using Cursor's agent mode report 40% fewer WIP PRs because devs complete full features in one session, changing code review patterns.'

### Fail Examples

- Feature comparison table with checkmarks

---

## 5. ca_formatting

**Category:** presentation
**Description:** Memo is executive-ready with summary, comparison table, and clear sections

**Pass Condition:** Executive summary (1 paragraph). Comparison matrix/table. Detailed analysis per dimension. Recommendation section. Appendix with methodology.

**Scoring Method:** `weighted_components`
**Max Points:** 6

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `exec_summary` | 30% | 1-paragraph executive summary with recommendation | 1.0 if clear summary, 0.0 if missing |
| `comparison_table` | 35% | At-a-glance comparison matrix | 1.0 if clear matrix, 0.5 if partial, 0.0 if no table |
| `section_organization` | 35% | Clear sections with headers, consistent structure | 1.0 if well-organized, 0.5 if mostly, 0.0 if disorganized |

### Pass Examples

- Executive summary → Comparison matrix → Detailed analysis (8 dimensions) → Recommendation → Rollout plan → Appendix

### Fail Examples

- Wall of prose with no structure

---
