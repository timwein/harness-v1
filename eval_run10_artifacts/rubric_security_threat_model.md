# Rubric: security_analysis

**Task:** Produce a STRIDE threat model for a mobile banking app with biometric auth, P2P payments, and third-party integrations, including threat matrix, risk ratings, and prioritized mitigations

**Domain:** security_analysis
**Total Points:** 56
**Pass Threshold:** 85%
**Criteria Count:** 5
**Generated:** 2026-03-31 05:57:40 UTC

---

## 1. tm_stride_coverage

**Category:** methodology
**Description:** All 6 STRIDE categories applied systematically to each component

**Pass Condition:** Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege — each applied to biometric auth, P2P payments, and third-party integrations. At least 15 distinct threats identified.

**Scoring Method:** `weighted_components`
**Max Points:** 14

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `stride_completeness` | 30% | All 6 STRIDE categories addressed | % of STRIDE categories with at least one threat (6/6 = 1.0) |
| `component_coverage` | 30% | Threats identified for all 3 major components | 1.0 if all 3 components analyzed, 0.5 if 2, 0.0 if 1 |
| `threat_count` | 20% | At least 15 distinct, non-trivial threats | 1.0 if 15+, 0.7 if 10-14, 0.5 if 7-9, 0.0 if <7 |
| `threat_specificity` | 20% | Threats are specific to this app, not generic security advice | % of threats specific to mobile banking with biometric/P2P context |

### Pass Examples

- Spoofing/Biometric: Presentation attack using 3D-printed fingerprint or photo replay against face recognition on devices without dedicated secure enclave

### Fail Examples

- 'Spoofing: attacker could impersonate a user' — generic, not specific to biometric/mobile

---

## 2. tm_risk_rating

**Category:** analysis
**Description:** Risk ratings use a consistent framework (DREAD, CVSS, or custom) with justification

**Pass Condition:** Each threat has: likelihood, impact, and combined risk score. Uses consistent rating framework. Justifies ratings, not arbitrary numbers.

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `framework_consistency` | 30% | Uses a named risk framework applied consistently | 1.0 if DREAD/CVSS/custom applied to all, 0.5 if inconsistent, 0.0 if no framework |
| `rating_justification` | 35% | Ratings justified with reasoning, not arbitrary | % of threats with justified ratings (not just 'High') |
| `likelihood_impact_separation` | 35% | Separately assesses likelihood and impact | 1.0 if both dimensions, 0.5 if combined only, 0.0 if single rating |

### Pass Examples

- Likelihood: Medium (requires physical device access + enrolled fingerprint bypass); Impact: Critical (full account takeover); Risk: High

### Fail Examples

- Risk: High — no reasoning or framework

---

## 3. tm_mitigations

**Category:** remediation
**Description:** Mitigations are specific, prioritized, and technically feasible

**Pass Condition:** Each threat has at least one mitigation. Mitigations are specific technical controls, not vague advice. Prioritized by risk rating. Include defense-in-depth layers.

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `mitigation_specificity` | 35% | Specific technical controls, not generic advice | % of mitigations that name specific technologies/patterns |
| `prioritization` | 25% | Mitigations ordered by risk, with implementation phases | 1.0 if phased implementation plan, 0.5 if prioritized list, 0.0 if unprioritized |
| `defense_in_depth` | 25% | Multiple layers of defense for critical threats | 1.0 if critical threats have 2+ mitigations, 0.5 if single layer, 0.0 if none |
| `feasibility` | 15% | Mitigations are implementable given mobile app constraints | 1.0 if all feasible, 0.5 if some unrealistic, 0.0 if impractical |

### Pass Examples

- Mitigation: (1) Require liveness detection via 3D face mapping, (2) Bind biometric to device TEE, (3) Step-up to SMS OTP for transactions >$500

### Fail Examples

- Mitigation: 'Use strong authentication' or 'Follow OWASP guidelines'

---

## 4. tm_threat_matrix

**Category:** structure
**Description:** Threat matrix is well-organized with clear cross-referencing

**Pass Condition:** Matrix/table format with: threat ID, STRIDE category, component, description, risk rating, mitigations. Sortable/filterable by category and priority.

**Scoring Method:** `weighted_components`
**Max Points:** 8

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `tabular_format` | 35% | Clear matrix/table format, not just prose | 1.0 if proper table with consistent columns, 0.5 if semi-structured, 0.0 if prose only |
| `cross_referencing` | 30% | Threats linked to mitigations by ID | 1.0 if IDs cross-referenced, 0.5 if inline, 0.0 if disconnected |
| `executive_summary` | 35% | Summary of critical findings and top-priority actions | 1.0 if exec summary at top, 0.0 if missing |

### Pass Examples

- | T-01 | Spoofing | Biometric Auth | Fingerprint replay attack | High | M-01, M-02 |

### Fail Examples

- Unstructured list of security concerns

---

## 5. tm_domain_depth

**Category:** expertise
**Description:** Demonstrates deep knowledge of mobile banking security, not generic application security

**Pass Condition:** References: PSD2/SCA requirements, mobile platform security (TEE, Keystore, Secure Enclave), payment network rules, biometric standards (FIDO2), and regulatory requirements.

**Scoring Method:** `weighted_components`
**Max Points:** 10

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `regulatory_awareness` | 30% | References PSD2, PCI-DSS, or relevant financial regulations | 1.0 if specific regulatory references, 0.5 if generic compliance mention, 0.0 if absent |
| `platform_specifics` | 35% | Addresses iOS/Android specific security controls (TEE, Keychain) | 1.0 if platform-specific controls, 0.5 if generic mobile, 0.0 if desktop-centric |
| `payment_standards` | 35% | References payment-specific standards (EMV, tokenization) | 1.0 if payment standards referenced, 0.5 if basic, 0.0 if no payment context |

### Pass Examples

- 'P2P payments must comply with PSD2 SCA requirements — biometric alone satisfies one factor (inherence), but we need a second factor for transactions over EUR 30'

### Fail Examples

- Generic OWASP Mobile Top 10 without banking-specific context

---
