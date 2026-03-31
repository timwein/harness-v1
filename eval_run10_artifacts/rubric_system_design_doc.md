# Rubric: system_design

**Task:** Write a system design document for a real-time collaborative document editor supporting 100K concurrent users, covering CRDT vs OT tradeoffs, conflict resolution, persistence layer, and operational concerns

**Domain:** system_design
**Total Points:** 56
**Pass Threshold:** 85%
**Criteria Count:** 5
**Generated:** 2026-03-31 05:57:50 UTC

---

## 1. sd_crdt_ot

**Category:** technical_depth
**Description:** CRDT vs OT analysis is technically accurate with clear tradeoff reasoning

**Pass Condition:** Correctly explains both approaches. Compares: convergence guarantees, intent preservation, tombstone overhead, operational complexity. Makes a justified choice for this system. Mentions specific algorithms (Yjs/Automerge for CRDT, Jupiter/Google Wave OT).

**Scoring Method:** `weighted_components`
**Max Points:** 14

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `technical_accuracy` | 35% | Both CRDT and OT correctly explained at algorithmic level | 1.0 if algorithmically correct, 0.5 if conceptually right, 0.0 if errors |
| `tradeoff_analysis` | 30% | Compares on multiple dimensions with clear reasoning | 1.0 if multi-dimensional comparison, 0.5 if surface-level, 0.0 if one-sided |
| `justified_choice` | 20% | Clear recommendation with rationale tied to requirements | 1.0 if justified choice, 0.5 if stated preference, 0.0 if no recommendation |
| `algorithm_specifics` | 15% | Names specific algorithms/libraries (Yjs, Automerge, Jupiter) | 1.0 if specific algorithms, 0.5 if general approach, 0.0 if abstract only |

### Pass Examples

- CRDT (Yjs YATA algorithm) chosen over OT: no central server for transform, better offline support. Tradeoff: tombstone garbage collection needed, metadata overhead ~30% for active documents.

### Fail Examples

- 'CRDTs are better than OT because they're newer' — no technical analysis

---

## 2. sd_architecture

**Category:** design
**Description:** System architecture supports 100K concurrent users with clear component diagram

**Pass Condition:** Architecture with: WebSocket gateway, document service, storage layer, presence service, auth layer. Horizontal scaling strategy. Component interaction diagram or description. Load distribution strategy.

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `component_design` | 30% | All required components identified with clear responsibilities | % of required components (gateway, doc service, storage, presence, auth) |
| `scaling_strategy` | 35% | Horizontal scaling with sharding/partitioning for 100K users | 1.0 if sharding strategy per document/user, 0.5 if generic 'add more servers', 0.0 if not addressed |
| `interaction_model` | 35% | Clear component interaction (sync vs async, protocols) | 1.0 if interaction diagram + protocol description, 0.5 if partial, 0.0 if unclear |

### Pass Examples

- Documents partitioned by doc_id hash across N document servers. WebSocket gateway routes connections to correct partition. Presence broadcast via Redis pub/sub.

### Fail Examples

- 'Use microservices and a load balancer' — no specific design

---

## 3. sd_conflict_resolution

**Category:** correctness
**Description:** Conflict resolution handles all edge cases: concurrent edits, offline, and reconnection

**Pass Condition:** Handles: simultaneous edits to same position, offline edit merging, client reconnection with state sync, undo/redo in collaborative context. Describes merge semantics for different operation types (insert, delete, format).

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `concurrent_edits` | 30% | Handles simultaneous edits with deterministic merge | 1.0 if deterministic merge described, 0.5 if mentioned, 0.0 if not addressed |
| `offline_support` | 30% | Offline edits can be merged on reconnection | 1.0 if offline merge strategy, 0.5 if acknowledged, 0.0 if ignored |
| `operation_types` | 25% | Merge semantics differ by operation type (insert vs delete vs format) | 1.0 if operation-specific semantics, 0.5 if generic, 0.0 if one-size-fits-all |
| `undo_redo` | 15% | Collaborative undo that doesn't undo other users' changes | 1.0 if selective undo described, 0.5 if acknowledged, 0.0 if ignored |

### Pass Examples

- Concurrent inserts at same position: use client_id as tiebreaker for deterministic ordering. Offline: client accumulates ops, on reconnect sends vector clock + pending ops, server rebases.

### Fail Examples

- 'Last write wins' — no real conflict resolution

---

## 4. sd_persistence

**Category:** storage
**Description:** Persistence layer handles document storage, versioning, and crash recovery

**Pass Condition:** Describes: document format (ops log vs snapshots), compaction strategy, write-ahead logging for crash recovery, versioning for history/undo, and snapshot frequency tradeoffs.

**Scoring Method:** `weighted_components`
**Max Points:** 10

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `storage_model` | 30% | Clear model: ops log, snapshots, or hybrid with rationale | 1.0 if hybrid with rationale, 0.5 if single approach, 0.0 if not specified |
| `compaction` | 25% | Strategy for compacting operation log to prevent unbounded growth | 1.0 if compaction/snapshot strategy, 0.5 if acknowledged, 0.0 if ignored |
| `crash_recovery` | 25% | WAL or equivalent for crash recovery without data loss | 1.0 if WAL/recovery strategy, 0.5 if basic durability, 0.0 if not addressed |
| `versioning` | 20% | Document history and version access for users | 1.0 if version history with access, 0.5 if basic, 0.0 if absent |

### Pass Examples

- Ops log for real-time (Redis Streams), periodic snapshots to S3 (every 1000 ops or 5 min), snapshot + replay for crash recovery. History via snapshot chain.

### Fail Examples

- 'Store documents in a database' — no specifics

---

## 5. sd_operational

**Category:** production_readiness
**Description:** Addresses operational concerns: monitoring, graceful degradation, SLOs, deployment

**Pass Condition:** Defines: SLOs for latency and consistency, monitoring dashboards, graceful degradation under load, zero-downtime deployment strategy, and capacity planning for 100K concurrent users.

**Scoring Method:** `weighted_components`
**Max Points:** 8

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `slos` | 25% | Specific SLOs for latency, consistency, and availability | 1.0 if numeric SLOs (e.g., p99 <200ms, 99.9% uptime), 0.5 if qualitative, 0.0 if absent |
| `monitoring` | 25% | Key metrics and dashboards for operational visibility | 1.0 if specific metrics (ops/sec, connection count, merge latency), 0.5 if generic, 0.0 if absent |
| `degradation` | 25% | Graceful degradation under load (read-only mode, reduced sync frequency) | 1.0 if specific degradation strategy, 0.5 if acknowledged, 0.0 if not addressed |
| `capacity_planning` | 25% | Back-of-envelope capacity estimates for 100K concurrent users | 1.0 if quantified (connections, bandwidth, storage), 0.5 if estimated, 0.0 if not addressed |

### Pass Examples

- 100K users × ~1 op/sec avg = 100K ops/sec. Each op ~200 bytes → 20 MB/s ingest. 10 document servers at 10K connections each. SLO: p99 sync <200ms, data loss window <5s.

### Fail Examples

- 'The system should be highly available and performant' — no specifics

---
