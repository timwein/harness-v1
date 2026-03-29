# Rubric: billing_schema

**Domain:** schema_design
**Total Points:** 38
**Pass Threshold:** 0.85

## Criterion 1: schema_completeness
**Category:** design
**Max Points:** N/A
**Description:** Schema includes all core billing entities with appropriate relationships
**Pass Condition:** Must include entities: tenant, plan, subscription, usage_record, invoice, line_item. Must support pricing models: per-seat, usage-based (metered), tiered pricing. Must include billing cycle configuration, proration handling, and trial period support. Each missing entity/model/feature = -1 point from max 12.

## Criterion 2: schema_correctness
**Category:** quality
**Max Points:** N/A
**Description:** Valid JSON Schema with proper types, constraints, references
**Pass Condition:** Valid JSON Schema (draft-07+) with zero validation errors when tested against sample data. Must use $ref for reuse across 3+ entity definitions. Required fields marked with validation rules (minLength, format constraints). Enums for constrained values with at least 3 options each. Proper date-time formats with timezone handling. Must include pattern validation for IDs and email formats.

## Criterion 3: schema_extensibility
**Category:** architecture
**Max Points:** N/A
**Description:** Schema supports future extensions without breaking existing integrations
**Pass Condition:** Uses additionalProperties: true on root objects, additionalProperties: false on strict constraint objects. Includes version field in schema. Metered usage dimensions defined as array/list structure (not hardcoded properties). Includes extensible metadata object on tenant, plan, and subscription entities.

## Criterion 4: schema_realworld
**Category:** practicality
**Max Points:** N/A
**Description:** Schema models production billing system patterns with proper data integrity
**Pass Condition:** Must include: idempotency_key fields on mutation-triggering entities, invoice status enum (draft/open/paid/void/uncollectible), webhook_event schema, multi-currency support with currency codes. Must NOT store calculated totals without corresponding line items. Must model subscription state transitions properly.
