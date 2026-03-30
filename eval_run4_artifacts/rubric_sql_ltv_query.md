# SQL LTV Query — Rubric

**Task:** Create a SQL query to find the top 10 customers by lifetime value excluding refunds, from a schema you define
**Domain:** sql_query
**Total Points:** 36
**Pass Threshold:** 85%

---

## sql_schema

**Category:** design

**Description:** Schema is realistic, normalized, and supports the query requirements

**Pass Condition:** Separate customers, orders, order_items, payments/refunds tables. Proper PKs/FKs. Realistic column types. Refunds modeled distinctly from payments.

**Scoring Method:** WEIGHTED_COMPONENTS (max 10 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| normalization | Proper 3NF with PKs/FKs | 0.30 | 1.0 if 3NF, 0.5 if some denormalization, 0.0 if flat |
| refund_modeling | Refunds modeled as distinct records, not negative amounts | 0.35 | 1.0 if refund table or refund_type flag, 0.5 if negative amounts, 0.0 if not modeled |
| realistic_columns | Realistic types, constraints, timestamps | 0.35 | % of tables with appropriate types and constraints |

**Pass Examples:** customers, orders, order_items, payments (with type: 'charge'|'refund') + indexes

**Fail Examples:** Single 'transactions' table with all data flattened

---

## sql_correctness

**Category:** functionality

**Description:** Query returns correct results — top 10 by LTV excluding refunds

**Pass Condition:** Correctly aggregates payments minus refunds per customer. Uses proper GROUP BY, HAVING, ORDER BY DESC LIMIT 10. Handles NULL edge cases.

**Scoring Method:** WEIGHTED_COMPONENTS (max 12 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| aggregation_logic | SUM(charges) - SUM(refunds) or equivalent | 0.40 | 1.0 if correct LTV calc, 0.5 if close, 0.0 if wrong |
| grouping | Proper GROUP BY customer with ORDER BY + LIMIT | 0.30 | 1.0 if correct, 0.0 if missing or wrong |
| null_handling | COALESCE or equivalent for customers with no refunds | 0.30 | 1.0 if handles nulls, 0.5 if partially, 0.0 if would fail on nulls |

**Pass Examples:** `COALESCE(SUM(CASE WHEN type='charge' THEN amount END), 0) - COALESCE(SUM(CASE WHEN type='refund' THEN amount END), 0)`

**Fail Examples:** `SELECT * FROM customers ORDER BY amount` — no aggregation

---

## sql_readability

**Category:** quality

**Description:** Query is well-formatted, commented, and uses CTEs appropriately

**Pass Condition:** Uses CTEs for complex subqueries. Consistent formatting. Meaningful aliases. Comments on non-obvious logic.

**Scoring Method:** WEIGHTED_COMPONENTS (max 8 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| cte_usage | Uses CTEs for readability instead of nested subqueries | 0.35 | 1.0 if CTEs for distinct logical steps, 0.5 if inline subqueries, 0.0 if spaghetti |
| formatting | Consistent capitalization, indentation, line breaks | 0.30 | 1.0 if clean formatting, 0.5 if mostly ok, 0.0 if unformatted |
| documentation | Comments on key logic, meaningful aliases | 0.35 | 1.0 if commented + good aliases, 0.5 if one, 0.0 if neither |

**Pass Examples:** `WITH customer_charges AS (...), customer_refunds AS (...) SELECT ...`

**Fail Examples:** One-liner with nested subqueries and single-letter aliases

---

## sql_performance

**Category:** optimization

**Description:** Query would perform well at scale (millions of rows)

**Pass Condition:** Suggests or includes appropriate indexes. Avoids SELECT *. Doesn't use correlated subqueries. Notes on execution plan.

**Scoring Method:** PENALTY_BASED (max 6 pts)

| Penalty | Points Deducted |
|---|---|
| select_star | -1.5 |
| correlated_subquery | -2.0 |
| missing_index_suggestion | -1.0 |
| cartesian_join_risk | -2.5 |
| function_on_indexed_column | -1.0 |

**Pass Examples:** Index on payments(customer_id, type, amount), avoids correlated subqueries

**Fail Examples:** SELECT * with correlated subquery per customer row
