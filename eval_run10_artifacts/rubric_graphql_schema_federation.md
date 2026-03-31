# Rubric: api_design

**Task:** Design a federated GraphQL schema for an e-commerce platform spanning 4 subgraphs (users, products, orders, payments) with proper entity resolution, auth directives, and N+1 prevention

**Domain:** api_design
**Total Points:** 54
**Pass Threshold:** 85%
**Criteria Count:** 5
**Generated:** 2026-03-31 05:57:31 UTC

---

## 1. gql_subgraph_design

**Category:** architecture
**Description:** 4 subgraphs with clear domain boundaries and proper entity ownership

**Pass Condition:** Each subgraph owns its domain types. Entity references use @key directive. No circular dependencies between subgraphs. Shared types handled via @shareable. Each subgraph can be deployed independently.

**Scoring Method:** `weighted_components`
**Max Points:** 14

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `domain_boundaries` | 30% | Each subgraph owns distinct types with no overlap | % of types correctly owned by single subgraph |
| `entity_keys` | 35% | @key directives on all cross-subgraph entities | 1.0 if all entities have @key, 0.5 if most, 0.0 if missing |
| `independence` | 35% | Subgraphs can be deployed independently without breaking others | 1.0 if independent deployment possible, 0.5 if mostly, 0.0 if tightly coupled |

### Pass Examples

- type User @key(fields: "id") in users subgraph; type Order @key(fields: "id") extends User @external in orders subgraph

### Fail Examples

- All types in one schema, or circular type ownership

---

## 2. gql_entity_resolution

**Category:** correctness
**Description:** Entity resolution and reference resolvers are correctly defined across subgraphs

**Pass Condition:** __resolveReference implementations for all extended types. Proper @external and @requires annotations. Handles entity not found (null vs error). Batch resolution for performance.

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `resolve_reference` | 30% | __resolveReference defined for all cross-subgraph entities | % of extended entities with resolvers |
| `external_requires` | 30% | Correct use of @external and @requires for computed fields | 1.0 if correct annotations, 0.5 if partial, 0.0 if missing |
| `error_handling` | 20% | Entity not found returns null or typed error, not crash | 1.0 if handled, 0.0 if unhandled |
| `batch_resolution` | 20% | Batch/dataloader pattern for entity resolution | 1.0 if batched, 0.5 if individual, 0.0 if not addressed |

### Pass Examples

- __resolveReference({ id }) => dataLoader.load(id) — batches entity lookups

### Fail Examples

- No __resolveReference, or individual DB queries per entity

---

## 3. gql_auth

**Category:** security
**Description:** Auth directives provide field-level access control across subgraphs

**Pass Condition:** Custom @auth or @requiresAuth directive with role-based access. Applied at both type and field level. Gateway-level auth propagation. Handles unauthenticated access gracefully.

**Scoring Method:** `weighted_components`
**Max Points:** 10

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `directive_design` | 35% | Custom auth directive with role support | 1.0 if custom directive with roles, 0.5 if basic auth check, 0.0 if no auth |
| `field_level` | 30% | Auth applied at field level, not just type level | 1.0 if field-level (e.g., email only for ADMIN), 0.5 if type-level only, 0.0 if none |
| `propagation` | 35% | Auth context propagated from gateway to subgraphs | 1.0 if context propagation documented, 0.5 if implicit, 0.0 if not addressed |

### Pass Examples

- directive @auth(requires: Role = USER) on FIELD_DEFINITION; type User { email: String @auth(requires: ADMIN) }

### Fail Examples

- No auth directives, or only at the resolver level with no schema visibility

---

## 4. gql_n_plus_one

**Category:** performance
**Description:** N+1 prevention strategy is comprehensive — DataLoader, query planning, caching

**Pass Condition:** DataLoader pattern for all entity resolution. @defer for expensive fields. Query plan analysis showing batch optimization. Caching strategy for hot entities. Pagination on all list fields.

**Scoring Method:** `weighted_components`
**Max Points:** 10

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `dataloader` | 35% | DataLoader pattern used for all cross-subgraph fetches | 1.0 if DataLoader everywhere, 0.5 if some, 0.0 if none |
| `pagination` | 25% | All list fields use connection/pagination pattern | 1.0 if Relay-style connections, 0.5 if basic limit/offset, 0.0 if unbounded lists |
| `caching` | 20% | Caching strategy for frequently accessed entities | 1.0 if cache strategy documented, 0.5 if mentioned, 0.0 if absent |
| `query_complexity` | 20% | Query complexity/depth limiting to prevent abuse | 1.0 if complexity limits, 0.5 if depth limit, 0.0 if unbounded |

### Pass Examples

- orders(first: 20, after: cursor): OrderConnection! — with DataLoader for user resolution, Redis cache for product lookups

### Fail Examples

- orders: [Order!]! — unbounded list with N+1 user queries

---

## 5. gql_schema_quality

**Category:** design
**Description:** Schema follows GraphQL best practices: naming, nullability, input types, errors

**Pass Condition:** Consistent naming conventions. Proper nullability (nullable by default, ! where guaranteed). Input types for mutations. Union/interface for polymorphic types. Typed errors, not string messages.

**Scoring Method:** `weighted_components`
**Max Points:** 8

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `naming` | 25% | Consistent PascalCase types, camelCase fields, SCREAMING_SNAKE enums | 1.0 if consistent, 0.5 if mostly, 0.0 if inconsistent |
| `nullability` | 25% | Intentional nullability — not everything is non-null | 1.0 if thoughtful nullability, 0.5 if all non-null or all nullable, 0.0 if inconsistent |
| `input_types` | 25% | Mutations use dedicated input types, not inline args | 1.0 if input types for mutations, 0.5 if mixed, 0.0 if inline args only |
| `error_handling` | 25% | Typed errors via unions or result types, not just strings | 1.0 if union PaymentResult = Payment \| PaymentError, 0.5 if error extensions, 0.0 if string message |

### Pass Examples

- mutation createOrder(input: CreateOrderInput!): CreateOrderResult! where union CreateOrderResult = Order | InsufficientStockError | PaymentFailedError

### Fail Examples

- mutation createOrder(productId: ID!, quantity: Int!): Order! — no input type, no error type

---
