# Rubric: sql_query

**Task:** Create a SQL query to find the top 10 customers by lifetime value excluding refunds, from a schema you define

**Domain:** sql_query
**Total Points:** 36
**Pass Threshold:** 85%
**Criteria Count:** 4
**Generated:** 2026-03-31 05:56:30 UTC

---

## 1. sql_schema

**Category:** design
**Description:** Schema is realistic, normalized, and supports the query requirements

**Pass Condition:** Separate customers, orders, order_items, payments/refunds tables. Proper PKs/FKs. Realistic column types. Refunds modeled distinctly from payments.

**Scoring Method:** `weighted_components`
**Max Points:** 10

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `normalization` | 30% | Proper 3NF with PKs/FKs | 1.0 if 3NF, 0.5 if some denormalization, 0.0 if flat |
| `refund_modeling` | 35% | Refunds modeled as distinct records, not negative amounts | 1.0 if refund table or refund_type flag, 0.5 if negative amounts, 0.0 if not modeled |
| `realistic_columns` | 35% | Realistic types, constraints, timestamps | % of tables with appropriate types and constraints |

### Pass Examples

- customers, orders, order_items, payments (with type: 'charge'|'refund') + indexes

### Fail Examples

- Single 'transactions' table with all data flattened

---

## 2. sql_correctness

**Category:** functionality
**Description:** Query returns correct results — top 10 by LTV excluding refunds

**Pass Condition:** Correctly aggregates payments minus refunds per customer. Uses proper GROUP BY, HAVING, ORDER BY DESC LIMIT 10. Handles NULL edge cases.

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `aggregation_logic` | 40% | SUM(charges) - SUM(refunds) or equivalent | 1.0 if correct LTV calc, 0.5 if close, 0.0 if wrong |
| `grouping` | 30% | Proper GROUP BY customer with ORDER BY + LIMIT | 1.0 if correct, 0.0 if missing or wrong |
| `null_handling` | 30% | COALESCE or equivalent for customers with no refunds | 1.0 if handles nulls, 0.5 if partially, 0.0 if would fail on nulls |

### Pass Examples

- COALESCE(SUM(CASE WHEN type='charge' THEN amount END), 0) - COALESCE(SUM(CASE WHEN type='refund' THEN amount END), 0)

### Fail Examples

- SELECT * FROM customers ORDER BY amount — no aggregation

---

## 3. sql_readability

**Category:** quality
**Description:** Query is well-formatted, commented, and uses CTEs appropriately

**Pass Condition:** Uses CTEs for complex subqueries. Consistent formatting. Meaningful aliases. Comments on non-obvious logic.

**Scoring Method:** `weighted_components`
**Max Points:** 8

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `cte_usage` | 35% | Uses CTEs for readability instead of nested subqueries | 1.0 if CTEs for distinct logical steps, 0.5 if inline subqueries, 0.0 if spaghetti |
| `formatting` | 30% | Consistent capitalization, indentation, line breaks | 1.0 if clean formatting, 0.5 if mostly ok, 0.0 if unformatted |
| `documentation` | 35% | Comments on key logic, meaningful aliases | 1.0 if commented + good aliases, 0.5 if one, 0.0 if neither |

### Pass Examples

- WITH customer_charges AS (...), customer_refunds AS (...) SELECT ...

### Fail Examples

- One-liner with nested subqueries and single-letter aliases

---

## 4. sql_performance

**Category:** optimization
**Description:** Query would perform well at scale (millions of rows)

**Pass Condition:** Suggests or includes appropriate indexes. Avoids SELECT *. Doesn't use correlated subqueries. Notes on execution plan.

**Scoring Method:** `penalty_based`
**Max Points:** 6

### Penalties

- **select_star:** -1.5 pts
- **correlated_subquery:** -2.0 pts
- **missing_index_suggestion:** -1.0 pts
- **cartesian_join_risk:** -2.5 pts
- **function_on_indexed_column:** -1.0 pts

### Pass Examples

- Index on payments(customer_id, type, amount), avoids correlated subqueries

### Fail Examples

- SELECT * with correlated subquery per customer row

---
