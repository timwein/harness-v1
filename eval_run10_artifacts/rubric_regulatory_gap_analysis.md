# Rubric: compliance

**Task:** Perform a SOC 2 Type II readiness gap analysis for a 50-person B2B SaaS startup, identifying control gaps across all 5 trust service criteria with remediation priorities and estimated timelines

**Domain:** compliance
**Total Points:** 52
**Pass Threshold:** 85%
**Criteria Count:** 5
**Generated:** 2026-03-31 05:57:59 UTC

---

## 1. soc2_tsc_coverage

**Category:** completeness
**Description:** All 5 Trust Service Criteria systematically assessed

**Pass Condition:** Security, Availability, Processing Integrity, Confidentiality, and Privacy — each with specific control objectives evaluated. References actual AICPA criteria (CC1–CC9 series).

**Scoring Method:** `weighted_components`
**Max Points:** 14

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `tsc_coverage` | 35% | All 5 TSC categories addressed with specific controls | % of TSC categories with detailed control assessment (5/5 = 1.0) |
| `criteria_references` | 30% | References specific CC criteria (CC1.1, CC6.1, etc.) | 1.0 if specific criteria referenced, 0.5 if category-level, 0.0 if generic |
| `control_depth` | 35% | Each TSC has 3+ specific controls evaluated | 1.0 if 3+ controls per TSC, 0.5 if 1-2, 0.0 if surface-level |

### Pass Examples

- CC6.1 (Logical Access): Current state — SSO via Google Workspace, no MFA enforced for CLI/API access. Gap: MFA not required for all access paths.

### Fail Examples

- 'Security: needs improvement. Availability: mostly good.' — no specific controls

---

## 2. soc2_gap_specificity

**Category:** analysis
**Description:** Gaps are specific to a 50-person startup context, not generic compliance advice

**Pass Condition:** Gaps reflect startup reality: limited security team, rapid deployment, shared infrastructure, informal processes. At least 12 specific gaps identified. Each gap states current state vs required state.

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `startup_context` | 35% | Gaps reflect realistic startup gaps (no CISO, shared accounts, etc.) | % of gaps that are realistic for a 50-person startup |
| `current_vs_required` | 30% | Each gap states 'what is' vs 'what should be' | % of gaps with explicit current/required comparison |
| `gap_count` | 20% | At least 12 specific, non-trivial gaps identified | 1.0 if 12+, 0.7 if 8-11, 0.5 if 5-7, 0.0 if <5 |
| `evidence_basis` | 15% | Gaps based on observable evidence, not assumptions | 1.0 if evidence-based, 0.5 if reasonable assumptions, 0.0 if generic |

### Pass Examples

- Gap: No formal change management process — developers deploy to production via direct git push to main. Required: Documented change management with approval workflow, testing requirements, and rollback procedures (CC8.1).

### Fail Examples

- 'The company needs better security controls' — no specifics

---

## 3. soc2_remediation

**Category:** planning
**Description:** Remediation plan is prioritized, resource-aware, and has realistic timelines

**Pass Condition:** Gaps prioritized by audit risk and effort. Each remediation has: specific action, responsible role, estimated effort (person-weeks), timeline, and dependencies. Total timeline realistic for a startup (3-6 months, not 2 years).

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `prioritization` | 30% | Remediation prioritized by audit risk (not just effort) | 1.0 if risk-based priority, 0.5 if effort-based, 0.0 if unprioritized |
| `actionability` | 30% | Each remediation is a specific deliverable with responsible party | % of remediations with specific action + owner |
| `timeline_realism` | 20% | Total timeline is realistic for a 50-person startup | 1.0 if 3-6 months, 0.5 if 6-12 months, 0.0 if unrealistic |
| `resource_awareness` | 20% | Acknowledges limited security team and suggests pragmatic approaches | 1.0 if pragmatic (e.g., 'use managed service X instead of building'), 0.5 if aware, 0.0 if enterpris |

### Pass Examples

- Priority 1 (Week 1-2): Enforce MFA via Google Workspace admin settings — 2 hours effort, IT lead. Unblocks all access control controls.

### Fail Examples

- 'Implement a comprehensive security program' — no timeline, no specifics

---

## 4. soc2_tooling

**Category:** practicality
**Description:** Recommends specific tools and platforms appropriate for startup scale

**Pass Condition:** Names specific compliance platforms (Vanta, Drata, Secureframe). Recommends specific technical controls (not just 'use encryption'). Suggests automation where possible. Cost-conscious.

**Scoring Method:** `weighted_components`
**Max Points:** 8

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `platform_recommendation` | 30% | Names specific compliance automation platform | 1.0 if specific platform with reasoning, 0.5 if category, 0.0 if none |
| `technical_controls` | 35% | Specific tool/service recommendations per gap | % of gaps with named tool/service recommendation |
| `cost_awareness` | 35% | Considers startup budget constraints in recommendations | 1.0 if cost-conscious (free tier, startup programs), 0.5 if mentioned, 0.0 if enterprise pricing |

### Pass Examples

- Use Vanta ($15K/yr startup plan) for continuous compliance monitoring. For endpoint management, deploy Fleet (open source) rather than Jamf ($50K+ enterprise).

### Fail Examples

- 'Implement a SIEM solution' — no specific product, no cost consideration

---

## 5. soc2_audit_readiness

**Category:** judgment
**Description:** Includes practical audit preparation guidance beyond just fixing gaps

**Pass Condition:** Policy templates needed. Evidence collection strategy. Auditor selection advice. Type I vs Type II sequencing recommendation. Observation period planning.

**Scoring Method:** `weighted_components`
**Max Points:** 6

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `policy_guidance` | 35% | Lists specific policies needed with templates or outlines | 1.0 if policy list with scope/content guidance, 0.5 if list only, 0.0 if absent |
| `evidence_strategy` | 30% | How to collect and organize evidence during observation period | 1.0 if evidence collection plan, 0.5 if mentioned, 0.0 if absent |
| `audit_sequencing` | 35% | Type I → Type II recommendation with timing | 1.0 if sequencing advice, 0.0 if not addressed |

### Pass Examples

- Recommended path: 3 months remediation → Type I audit (1 month) → 6-month observation period → Type II. Start evidence collection from Day 1 of remediation.

### Fail Examples

- No audit process guidance, just gap list

---
