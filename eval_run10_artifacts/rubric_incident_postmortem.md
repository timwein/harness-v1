# Rubric: incident_management

**Task:** Write a blameless incident postmortem for a 4-hour production outage caused by a cascading failure across 3 microservices, including timeline, root cause, contributing factors, and action items

**Domain:** incident_management
**Total Points:** 52
**Pass Threshold:** 85%
**Criteria Count:** 5
**Generated:** 2026-03-31 05:57:28 UTC

---

## 1. pm_timeline

**Category:** structure
**Description:** Timeline is detailed, minute-level, and covers detection → mitigation → resolution

**Pass Condition:** Timestamped entries from first alert to all-clear. Covers detection, escalation, diagnosis attempts, mitigation, resolution, follow-up. At least 10 distinct timeline entries spanning the 4-hour window.

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `granularity` | 30% | Minute-level timestamps with clear event descriptions | 1.0 if minute-level with 10+ entries, 0.5 if hourly, 0.0 if vague |
| `coverage` | 35% | Covers full lifecycle: detect → escalate → diagnose → mitigate → resolve | % of lifecycle phases covered |
| `cascade_visibility` | 35% | Shows how failure propagated across the 3 services | 1.0 if cascade chain is explicit with per-service impact, 0.0 if lumped together |

### Pass Examples

- 14:03 — Auth service latency spikes to 8s → 14:07 — Payment service circuit breaker trips → 14:12 — Order service queue depth exceeds 50K

### Fail Examples

- 'Around 2pm things started going wrong and by 6pm we fixed it'

---

## 2. pm_root_cause

**Category:** analysis
**Description:** Root cause analysis is technically precise and distinguishes root from contributing causes

**Pass Condition:** Identifies a single root cause with technical specificity. Separates contributing factors (monitoring gaps, config drift, missing circuit breakers). Uses 5-whys or similar structured reasoning.

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `root_cause_precision` | 35% | Specific technical root cause, not vague hand-waving | 1.0 if pinpoints exact failure (e.g., connection pool exhaustion due to X), 0.0 if vague |
| `contributing_factors` | 30% | At least 3 contributing factors identified separately | 1.0 if 3+ factors clearly separated from root cause, 0.5 if mixed, 0.0 if absent |
| `structured_reasoning` | 35% | Uses 5-whys, fault tree, or similar analysis method | 1.0 if structured analysis visible, 0.5 if implicit, 0.0 if just narrative |

### Pass Examples

- Root cause: connection pool leak in auth-service v2.3.1 (PR #847) when Redis failover triggers reconnect storm. Contributing: no connection pool monitoring, stale circuit breaker config, no load shedding.

### Fail Examples

- 'The database went down and caused an outage'

---

## 3. pm_blamelessness

**Category:** tone
**Description:** Postmortem is genuinely blameless — focuses on systems, not individuals

**Pass Condition:** No person named as cause. Uses 'the system' not 'the engineer'. Frames gaps as process/tooling failures. Acknowledges what went right.

**Scoring Method:** `penalty_based`
**Max Points:** 10

### Penalties

- **names_individual_as_cause:** -4.0 pts
- **passive_aggressive_blame:** -3.0 pts
- **no_what_went_well_section:** -1.5 pts
- **punitive_action_items:** -2.0 pts
- **finger_pointing_language:** -2.0 pts

### Pass Examples

- 'The deployment pipeline lacked a canary stage' not 'Bob deployed without testing'

### Fail Examples

- 'The on-call engineer failed to notice the alert for 30 minutes'

---

## 4. pm_action_items

**Category:** remediation
**Description:** Action items are specific, owned, prioritized, and time-bound

**Pass Condition:** At least 5 action items. Each has: what, who (role not name), priority (P0-P2), deadline, and success metric. Mix of immediate fixes and systemic improvements.

**Scoring Method:** `weighted_components`
**Max Points:** 10

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `specificity` | 30% | Each action item is a concrete deliverable, not vague | 1.0 if all SMART-style, 0.5 if mixed, 0.0 if vague |
| `ownership_and_deadline` | 30% | Each item has owner (role) and timeline | % of items with both owner and deadline |
| `prioritization` | 20% | Items prioritized by impact, mix of quick fixes and systemic | 1.0 if P0/P1/P2 with rationale, 0.0 if unprioritized |
| `prevention_focus` | 20% | Items prevent recurrence, not just fix symptoms | 1.0 if systemic prevention, 0.5 if just patches, 0.0 if none |

### Pass Examples

- P0: Add connection pool monitoring with alert at 80% utilization — Platform team — 1 week — metric: alert fires in staging test

### Fail Examples

- 'Fix the bug', 'Be more careful', 'Add monitoring'

---

## 5. pm_impact_quantification

**Category:** completeness
**Description:** Impact is quantified across customer, business, and technical dimensions

**Pass Condition:** Quantifies: users affected, error rate, revenue impact, SLA breach, and customer-facing symptoms. Distinguishes partial vs total outage.

**Scoring Method:** `weighted_components`
**Max Points:** 8

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `customer_impact` | 35% | Number of users/requests affected, error rates | 1.0 if specific numbers, 0.5 if estimates, 0.0 if 'some users' |
| `business_impact` | 35% | Revenue/SLA implications quantified | 1.0 if dollar/SLA impact stated, 0.5 if acknowledged, 0.0 if missing |
| `symptom_description` | 30% | What customers actually experienced | 1.0 if customer-visible symptoms described, 0.0 if only internal view |

### Pass Examples

- 12,400 users saw 500 errors; 340 payment transactions failed ($48K GMV); 99.9% SLA breached for 3h47m

### Fail Examples

- 'There was a major outage affecting customers'

---
