# Rubric: code_generation

**Task:** Design and implement a Python token-bucket rate limiter with sliding window support, Redis backend, distributed coordination, and graceful degradation when Redis is unavailable

**Domain:** code_generation
**Total Points:** 56
**Pass Threshold:** 85%
**Criteria Count:** 5
**Generated:** 2026-03-31 05:57:29 UTC

---

## 1. rl_algorithm

**Category:** correctness
**Description:** Token bucket algorithm is correctly implemented with sliding window

**Pass Condition:** Proper token bucket: refill rate, bucket capacity, atomic consume. Sliding window tracks requests in time window, not fixed buckets. Handles burst vs sustained rate distinction.

**Scoring Method:** `weighted_components`
**Max Points:** 14

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `token_bucket_correctness` | 35% | Refill logic, capacity, atomic consume are correct | 1.0 if mathematically correct token bucket, 0.5 if close, 0.0 if wrong |
| `sliding_window` | 35% | True sliding window, not fixed-window bucketing | 1.0 if sliding window, 0.5 if fixed window, 0.0 if no windowing |
| `burst_handling` | 30% | Distinguishes burst allowance from sustained rate | 1.0 if configurable burst vs sustained, 0.5 if implicit, 0.0 if not addressed |

### Pass Examples

- Lua script for atomic check-and-decrement with ZRANGEBYSCORE for sliding window

### Fail Examples

- Simple counter with fixed-minute reset

---

## 2. rl_redis_integration

**Category:** infrastructure
**Description:** Redis operations are atomic, efficient, and handle distributed coordination

**Pass Condition:** Uses Lua scripts or MULTI/EXEC for atomicity. Proper key design with TTL. Handles Redis cluster mode. Connection pooling.

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `atomicity` | 40% | Rate check + consume is atomic (Lua script or pipeline) | 1.0 if Lua script, 0.7 if pipeline, 0.3 if separate commands, 0.0 if race-prone |
| `key_design` | 30% | Key naming scheme with TTL prevents unbounded growth | 1.0 if namespaced keys with TTL, 0.5 if TTL only, 0.0 if no TTL |
| `connection_management` | 30% | Connection pooling, proper cleanup, cluster-aware | 1.0 if pool + cluster-aware, 0.5 if pool only, 0.0 if per-request connections |

### Pass Examples

- Lua: local tokens = redis.call('GET', key); if tokens > 0 then redis.call('DECR', key) ...

### Fail Examples

- GET then SET with race condition between calls

---

## 3. rl_degradation

**Category:** resilience
**Description:** Graceful degradation when Redis is unavailable — doesn't block requests

**Pass Condition:** Falls back to in-memory rate limiting when Redis is down. Circuit breaker pattern for Redis health. Configurable fail-open vs fail-closed. Logs degradation state transitions.

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `fallback_mechanism` | 35% | In-memory fallback when Redis unreachable | 1.0 if local fallback with approximate rate limiting, 0.5 if fail-open only, 0.0 if crashes |
| `circuit_breaker` | 30% | Circuit breaker prevents hammering dead Redis | 1.0 if circuit breaker with half-open state, 0.5 if basic retry backoff, 0.0 if none |
| `configurability` | 35% | Fail-open vs fail-closed is configurable per use case | 1.0 if configurable with sensible default, 0.5 if hardcoded, 0.0 if not addressed |

### Pass Examples

- CircuitBreaker(failure_threshold=5, recovery_timeout=30) wrapping Redis calls; fallback to local TokenBucket

### Fail Examples

- try: redis.get() except: pass  # silently allow all traffic

---

## 4. rl_api_design

**Category:** usability
**Description:** Clean, well-typed API with decorator support and middleware integration

**Pass Condition:** Type-annotated. Usable as decorator (@rate_limit) and as middleware. Returns RateLimitResult with remaining/reset info. Async-compatible.

**Scoring Method:** `weighted_components`
**Max Points:** 10

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `type_safety` | 30% | Full type hints, dataclasses for config and results | 1.0 if complete typing, 0.5 if partial, 0.0 if none |
| `decorator_support` | 30% | Usable as @rate_limit(rate='100/min') decorator | 1.0 if decorator with config, 0.5 if basic, 0.0 if only function call |
| `async_support` | 20% | Works with both sync and async code | 1.0 if async-native with sync wrapper, 0.5 if sync only, 0.0 if broken |
| `response_metadata` | 20% | Returns remaining tokens, reset time, retry-after | 1.0 if RateLimitResult with all metadata, 0.5 if partial, 0.0 if bool only |

### Pass Examples

- @rate_limit(rate='100/min', burst=20, key=lambda req: req.client_ip)

### Fail Examples

- def check(key): return True/False  # no metadata, no typing

---

## 5. rl_testing

**Category:** quality
**Description:** Includes meaningful test scenarios covering edge cases and distributed behavior

**Pass Condition:** Test cases for: basic rate limiting, burst, window sliding, Redis failure fallback, concurrent access, key isolation. At least 6 test scenarios.

**Scoring Method:** `weighted_components`
**Max Points:** 8

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `coverage` | 50% | Tests cover happy path, edge cases, and failure modes | % of key scenarios covered (basic, burst, window, failover, concurrent, isolation) |
| `concurrent_testing` | 25% | Tests verify behavior under concurrent access | 1.0 if concurrent test with assertions, 0.5 if mentioned, 0.0 if absent |
| `test_quality` | 25% | Tests are isolated, readable, use fixtures | 1.0 if pytest-style with fixtures, 0.5 if basic, 0.0 if untestable |

### Pass Examples

- test_concurrent_requests_respect_limit(), test_redis_failover_uses_local_bucket()

### Fail Examples

- No tests, or a single 'test_it_works' function

---
