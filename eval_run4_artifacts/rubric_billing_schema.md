# Billing Schema — Rubric

**Task:** Design a JSON schema for a multi-tenant SaaS billing system supporting usage-based and seat-based pricing
**Domain:** schema_design
**Total Points:** 38
**Pass Threshold:** 85%

---

## schema_completeness

**Category:** design

**Description:** Schema covers all required entities and pricing models

**Pass Condition:** Entities: tenant, plan, subscription, usage_record, invoice, line_item. Pricing models: per-seat, usage-based (metered), tiered, hybrid. Billing cycles, proration, trial periods.

**Scoring Method:** WEIGHTED_COMPONENTS (max 12 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| entity_coverage | All required entities present | 0.30 | % of required entities modeled (tenant, plan, subscription, usage, invoice, line_item) |
| pricing_model_support | Both seat-based and usage-based modeled | 0.35 | 1.0 if both + hybrid, 0.75 if both, 0.5 if one, 0.0 if neither |
| billing_lifecycle | Cycles, proration, trials, upgrades/downgrades | 0.35 | % of lifecycle events modeled (create, upgrade, downgrade, cancel, prorate, trial) |

**Pass Examples:** Plan with pricing_model: {type: 'hybrid', seat_price: ..., metered_dimensions: [...]}

**Fail Examples:** Just 'plan' and 'subscription' with flat price field

---

## schema_correctness

**Category:** quality

**Description:** Valid JSON Schema with proper types, constraints, references

**Pass Condition:** Valid JSON Schema (draft-07+). Uses $ref for reuse. Required fields marked. Enums for constrained values. Proper date-time formats.

**Scoring Method:** WEIGHTED_COMPONENTS (max 10 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| schema_validity | Valid JSON Schema syntax | 0.30 | 1.0 if valid draft-07+, 0.5 if mostly valid, 0.0 if invalid |
| ref_usage | Uses $ref for reusable definitions | 0.25 | 1.0 if DRY with $ref, 0.5 if some reuse, 0.0 if duplicated |
| constraint_quality | Proper enums, required, formats, patterns | 0.45 | % of fields with appropriate constraints |

**Pass Examples:** $ref to shared 'money' type with currency+amount, enum for billing_interval

**Fail Examples:** Freeform JSON with no type constraints

---

## schema_extensibility

**Category:** architecture

**Description:** Schema is extensible without breaking changes

**Pass Condition:** Uses additionalProperties judiciously. Versioned. Metered dimensions are a list (not hardcoded). Custom metadata fields supported.

**Scoring Method:** WEIGHTED_COMPONENTS (max 8 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| metered_extensibility | Usage dimensions are dynamic, not hardcoded | 0.40 | 1.0 if array of dimension objects, 0.5 if a few named fields, 0.0 if hardcoded |
| metadata_support | Custom metadata/extension points | 0.30 | 1.0 if metadata object on key entities, 0.0 if closed |
| versioning | Schema version field or versioning strategy | 0.30 | 1.0 if versioned, 0.0 if not |

**Pass Examples:** metered_dimensions: [{id, unit, tiers: [...]}] — add new dimensions without schema change

**Fail Examples:** Hardcoded 'api_calls' and 'storage_gb' fields

---

## schema_realworld

**Category:** practicality

**Description:** Schema reflects real billing system patterns (Stripe-informed, not academic)

**Pass Condition:** Models concepts from real systems: idempotency keys, invoice status lifecycle, webhook events, currency handling. Avoids naive patterns (storing calculated totals without line items).

**Scoring Method:** PENALTY_BASED (max 8 pts)

| Penalty | Points Deducted |
|---|---|
| no_currency_handling | -2.0 |
| calculated_total_without_line_items | -2.0 |
| no_idempotency | -1.0 |
| no_invoice_status_lifecycle | -1.5 |
| naive_date_handling | -1.5 |
| single_currency_assumption | -1.0 |

**Pass Examples:** Invoice with status enum (draft→open→paid→void), line_items array, currency code per amount

**Fail Examples:** Invoice with just 'total: 99.99' and no line items
