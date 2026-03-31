# Rubric: data_engineering

**Task:** Design an Airflow DAG (Python) for an ETL pipeline that ingests from 3 sources (REST API, S3 parquet, PostgreSQL), handles schema drift, implements idempotent upserts, and includes alerting and retry logic

**Domain:** data_engineering
**Total Points:** 56
**Pass Threshold:** 85%
**Criteria Count:** 5
**Generated:** 2026-03-31 05:57:50 UTC

---

## 1. dag_structure

**Category:** architecture
**Description:** DAG is well-structured with proper task dependencies and separation of concerns

**Pass Condition:** Separate extract, transform, load tasks per source. Proper dependency graph. Uses TaskGroups or SubDAGs for source isolation. Sensor for data availability. DAG-level config (schedule, catchup, tags).

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `task_granularity` | 30% | E/T/L separated per source, not monolithic | 1.0 if E/T/L per source, 0.5 if partially separated, 0.0 if one giant task |
| `dependency_graph` | 35% | Dependencies model actual data flow accurately | 1.0 if correct DAG with parallelism where possible, 0.5 if linear, 0.0 if wrong |
| `dag_configuration` | 35% | Schedule, catchup=False, tags, retries, pool configured | % of config options set appropriately |

### Pass Examples

- TaskGroup per source with extract >> transform >> load, then join >> quality_check

### Fail Examples

- Single PythonOperator that does everything

---

## 2. dag_schema_drift

**Category:** resilience
**Description:** Handles schema drift without manual intervention

**Pass Condition:** Detects new/removed/changed columns from source. Applies schema evolution (add columns, type coercion). Alerts on breaking changes without crashing. Stores schema history for audit.

**Scoring Method:** `weighted_components`
**Max Points:** 14

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `detection` | 30% | Compares incoming schema against expected schema | 1.0 if schema comparison with diff, 0.5 if basic type checking, 0.0 if no detection |
| `evolution` | 35% | Auto-handles additive changes (new columns), alerts on breaking | 1.0 if auto-evolve + alert on breaking, 0.5 if one, 0.0 if crashes on drift |
| `schema_history` | 15% | Persists schema versions for audit trail | 1.0 if versioned schema store, 0.0 if not tracked |
| `type_coercion` | 20% | Handles type changes gracefully (string→int, nullable changes) | 1.0 if coercion with fallback, 0.5 if basic, 0.0 if crashes |

### Pass Examples

- SchemaEvolver.evolve(current_schema, incoming_schema) → AddColumn migrations + Slack alert for type changes

### Fail Examples

- Hardcoded column list that breaks when source adds a field

---

## 3. dag_idempotency

**Category:** correctness
**Description:** All operations are idempotent — safe to re-run without duplicates

**Pass Condition:** Upserts (not insert-only). Deduplication by natural key. Watermark-based incremental loads. Atomic write-and-swap for target tables.

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `upsert_pattern` | 35% | Uses UPSERT/MERGE, not blind INSERT | 1.0 if proper upsert with conflict resolution, 0.5 if delete+insert, 0.0 if insert only |
| `incremental_loads` | 30% | Watermark/timestamp-based incremental extraction | 1.0 if watermark with state tracking, 0.5 if date-parameterized, 0.0 if full reload |
| `deduplication` | 35% | Natural key deduplication with deterministic behavior | 1.0 if natural key dedup, 0.5 if row-level dedup, 0.0 if no dedup |

### Pass Examples

- INSERT ... ON CONFLICT (source_id, source_system) DO UPDATE SET ... WHERE updated_at > EXCLUDED.updated_at

### Fail Examples

- INSERT INTO target SELECT * FROM staging — duplicates on re-run

---

## 4. dag_error_handling

**Category:** reliability
**Description:** Comprehensive error handling with retries, alerting, and dead-letter patterns

**Pass Condition:** Task-level retries with exponential backoff. Dead-letter table for failed records. Slack/PagerDuty alerting on failure. SLA miss detection.

**Scoring Method:** `weighted_components`
**Max Points:** 10

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `retry_strategy` | 30% | Exponential backoff with configurable max retries | 1.0 if exponential backoff, 0.5 if fixed retries, 0.0 if no retries |
| `dead_letter` | 25% | Failed records captured for later investigation, not dropped | 1.0 if dead-letter table with error context, 0.0 if records dropped silently |
| `alerting` | 25% | Failure callbacks to Slack/PagerDuty with context | 1.0 if on_failure_callback with rich context, 0.5 if basic email, 0.0 if silent |
| `sla_monitoring` | 20% | SLA miss detection for pipeline lateness | 1.0 if SLA configured with alert, 0.0 if not addressed |

### Pass Examples

- default_args={'retries': 3, 'retry_delay': timedelta(minutes=5), 'retry_exponential_backoff': True, 'on_failure_callback': slack_alert}

### Fail Examples

- No retries, no alerting, failed records silently dropped

---

## 5. dag_code_quality

**Category:** quality
**Description:** Production-grade Python code with proper configuration management

**Pass Condition:** Configuration via Airflow Variables or YAML, not hardcoded. Custom operators or well-structured helper modules. Type hints. Connection management via Airflow hooks. Testable structure.

**Scoring Method:** `weighted_components`
**Max Points:** 8

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `configuration` | 35% | Connections/credentials via Airflow hooks and Variables, not hardcoded | 1.0 if all config via hooks/Variables, 0.5 if mixed, 0.0 if hardcoded |
| `modularity` | 30% | Reusable operators or helper modules, not inline lambdas | 1.0 if custom operators/modules, 0.5 if functions, 0.0 if inline |
| `typing_and_docs` | 35% | Type hints and docstrings on key functions | 1.0 if typed + documented, 0.5 if partial, 0.0 if neither |

### Pass Examples

- from dags.operators.schema_evolve import SchemaEvolveOperator; uses PostgresHook, S3Hook

### Fail Examples

- Hardcoded connection strings, 300-line DAG file with no helpers

---
