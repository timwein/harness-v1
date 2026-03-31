# Rubric: debugging

**Task:** Write a step-by-step debugging walkthrough for a race condition in a Node.js Express app where concurrent requests to a shared PostgreSQL connection pool cause intermittent 500 errors under load

**Domain:** debugging
**Total Points:** 56
**Pass Threshold:** 85%
**Criteria Count:** 5
**Generated:** 2026-03-31 05:57:34 UTC

---

## 1. dbg_reproduction

**Category:** diagnosis
**Description:** Provides a clear, minimal reproduction of the race condition

**Pass Condition:** Shows the vulnerable code pattern. Explains why it's intermittent. Provides a load test command or script to trigger the bug reliably. Identifies the exact window where the race occurs.

**Scoring Method:** `weighted_components`
**Max Points:** 14

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `vulnerable_code` | 30% | Shows a realistic code pattern that exhibits the race condition | 1.0 if realistic vulnerable code, 0.5 if abstract, 0.0 if no code |
| `race_window` | 35% | Explains the exact timing window where the race occurs | 1.0 if precise window identified (e.g., between pool.query() and release), 0.5 if general, 0.0 if va |
| `reproduction_method` | 35% | Provides a way to trigger the bug reliably | 1.0 if load test script/command, 0.5 if manual steps, 0.0 if 'just send lots of requests' |

### Pass Examples

- autocannon -c 100 -d 10 http://localhost:3000/api/transfer — triggers pool exhaustion in ~3 seconds when pool.max is 10

### Fail Examples

- 'Sometimes under load you might see 500 errors'

---

## 2. dbg_root_cause

**Category:** analysis
**Description:** Root cause analysis correctly identifies the concurrency mechanism causing the bug

**Pass Condition:** Identifies specific mechanism: connection pool exhaustion, connection leak, transaction isolation violation, or shared mutable state. Shows the event loop execution order that leads to the bug.

**Scoring Method:** `weighted_components`
**Max Points:** 14

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `mechanism_identification` | 35% | Correctly identifies the concurrency mechanism | 1.0 if precise mechanism (pool leak, isolation violation), 0.5 if close, 0.0 if wrong |
| `event_loop_reasoning` | 35% | Shows how Node.js event loop scheduling creates the race | 1.0 if event loop order demonstrated, 0.5 if mentioned, 0.0 if ignored |
| `state_analysis` | 30% | Identifies what shared state is being corrupted or exhausted | 1.0 if specific state identified, 0.5 if general, 0.0 if not analyzed |

### Pass Examples

- Connection acquired in handler A, awaits external API. Handler B acquires another connection. Pool exhausted at 10. Handler C awaits pool.connect() → timeout → 500. Root: connections not released on error paths.

### Fail Examples

- 'Too many concurrent requests cause the server to crash'

---

## 3. dbg_fix

**Category:** solution
**Description:** Fix is correct, addresses the root cause, and doesn't introduce new issues

**Pass Condition:** Shows before/after code. Fix addresses root cause (not just symptoms). Uses proper patterns (try/finally for connection release, pool.query shorthand, or serialized access). Includes connection leak prevention.

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `correctness` | 35% | Fix eliminates the race condition | 1.0 if race eliminated, 0.5 if mitigated, 0.0 if wrong fix |
| `root_cause_addressed` | 30% | Fix targets root cause, not symptoms (not just more connections) | 1.0 if root cause fixed, 0.5 if symptom treated, 0.0 if bandaid |
| `before_after` | 20% | Clear before/after code comparison | 1.0 if before/after, 0.5 if fix only, 0.0 if prose only |
| `no_regression` | 15% | Fix doesn't introduce new problems (deadlocks, performance) | 1.0 if considered, 0.5 if partially, 0.0 if not addressed |

### Pass Examples

- Before: const client = await pool.connect(); await query(); await query2(); client.release(); // release skipped if query2 throws. After: try { ... } finally { client.release(); } — or better: pool.query() for single-query handlers

### Fail Examples

- 'Increase the pool size to 100' — treats symptom, not cause

---

## 4. dbg_methodology

**Category:** process
**Description:** Debugging methodology is systematic and teaches transferable techniques

**Pass Condition:** Step-by-step process: observe → hypothesize → instrument → verify → fix → validate. Shows specific debugging tools (pg_stat_activity, pool events, async_hooks). Each step builds on the previous one logically.

**Scoring Method:** `weighted_components`
**Max Points:** 8

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `systematic` | 35% | Follows a logical debugging sequence, not random poking | 1.0 if structured methodology, 0.5 if semi-structured, 0.0 if ad hoc |
| `tooling` | 35% | Uses specific debugging tools for the Node.js/PostgreSQL stack | 1.0 if names specific tools (pg_stat_activity, pool.on('acquire'), clinic.js), 0.5 if generic, 0.0 i |
| `transferable` | 30% | Teaches principles applicable to other race conditions | 1.0 if generalizable lessons, 0.5 if task-specific only, 0.0 if not addressed |

### Pass Examples

- Step 1: Check pg_stat_activity for idle connections → Step 2: pool.on('acquire'/'release') logging → Step 3: Correlate with request traces → Step 4: Identify unreleased connections

### Fail Examples

- 'Look at the code until you find the bug'

---

## 5. dbg_prevention

**Category:** robustness
**Description:** Includes prevention measures to avoid similar race conditions in the future

**Pass Condition:** Recommends: connection pool monitoring, lint rules for connection management, load testing in CI, circuit breaker patterns, and code review checklist items.

**Scoring Method:** `weighted_components`
**Max Points:** 8

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `monitoring` | 30% | Pool monitoring with alerts for connection leaks | 1.0 if specific monitoring (pool size, wait time metrics), 0.5 if generic, 0.0 if absent |
| `code_patterns` | 35% | Recommends safe patterns (pool.query, try/finally, middleware) | 1.0 if safe patterns with code examples, 0.5 if mentioned, 0.0 if absent |
| `ci_integration` | 35% | Load testing or race condition detection in CI | 1.0 if CI integration, 0.5 if manual testing, 0.0 if not addressed |

### Pass Examples

- Add pool.on('remove') logging + Prometheus gauge for pool.waitingCount. CI: autocannon smoke test on /healthz that fails if p99 > 500ms.

### Fail Examples

- 'Be careful with concurrent code' — no actionable prevention

---
