# Rubric: sql_ltv_query

**Domain:** sql_query
**Total Points:** 36
**Pass Threshold:** 0.85

## Criterion 1: sql_schema
**Category:** design
**Max Points:** N/A
**Description:** Schema includes separate tables for customers, orders, order_items, and financial transactions with clear primary/foreign key relationships
**Pass Condition:** Must have: customers table with customer_id PK; orders table with order_id PK and customer_id FK; order_items table with order_item_id PK, order_id FK, and price/quantity fields; transactions/payments table with transaction_id PK, order_id FK, amount, and transaction_type field distinguishing payments from refunds (or separate refunds table). Schema must handle partial refunds (refund amount < order total) and include appropriate indexes on foreign keys. All PKs are appropriate data types (INT/UUID).

## Criterion 2: sql_correctness
**Category:** functionality
**Max Points:** N/A
**Description:** Query returns correct results — top 10 by LTV excluding refunds
**Pass Condition:** Correctly aggregates payments minus refunds per customer with proper handling of: (1) partial refunds that don't cancel entire orders, (2) customers with only refunded orders (negative LTV), (3) NULL transaction amounts. Uses proper GROUP BY customer_id, ORDER BY LTV DESC, LIMIT 10. Query must exclude customers with zero transactions entirely.

## Criterion 3: sql_readability
**Category:** quality
**Max Points:** N/A
**Description:** Query uses appropriate SQL structure and naming for clarity
**Pass Condition:** Query uses CTEs when main query logic exceeds 2 levels of nesting OR when aggregating the same data multiple times. All table aliases are 2+ meaningful characters (not c, o, p). Final SELECT includes customer identifier and calculated 'lifetime_value' with explicit column aliases. No ambiguous column references (all columns prefixed with table alias).

## Criterion 4: sql_performance
**Category:** optimization
**Max Points:** N/A
**Description:** Query avoids common performance anti-patterns for large datasets
**Pass Condition:** Query does not use SELECT * in final output. Does not use correlated subqueries (EXISTS/NOT EXISTS acceptable). Includes written justification for any full table scans or explains why specific indexes would help.
