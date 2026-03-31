# Rubric: systems_programming

**Task:** Implement a thread-safe LRU cache in Rust with TTL expiry, bounded memory, and lock-free reads using Arc, RwLock, and background eviction, including comprehensive error handling

**Domain:** systems_programming
**Total Points:** 56
**Pass Threshold:** 85%
**Criteria Count:** 5
**Generated:** 2026-03-31 05:57:21 UTC

---

## 1. rust_lru_correctness

**Category:** algorithm
**Description:** LRU eviction is correctly implemented with O(1) get/put

**Pass Condition:** Uses HashMap + doubly-linked list for O(1) operations. Eviction removes least-recently-used on capacity overflow. Get promotes entry to most-recently-used.

**Scoring Method:** `weighted_components`
**Max Points:** 14

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `data_structure` | 35% | HashMap + linked list or equivalent O(1) structure | 1.0 if O(1) get+put, 0.5 if O(log n), 0.0 if O(n) scan |
| `eviction_correctness` | 35% | LRU entry evicted when capacity exceeded | 1.0 if correct LRU eviction, 0.5 if FIFO, 0.0 if wrong/missing |
| `access_promotion` | 30% | Get operation promotes to most-recently-used | 1.0 if get promotes, 0.0 if get doesn't update order |

### Pass Examples

- struct LruCache<K, V> { map: HashMap<K, *mut Node<K, V>>, head: *mut Node, tail: *mut Node }

### Fail Examples

- Vec::remove(0) for eviction — O(n), not a real LRU

---

## 2. rust_concurrency

**Category:** thread_safety
**Description:** Thread safety is achieved with minimal lock contention

**Pass Condition:** Uses Arc<RwLock<...>> for shared ownership. Reads don't block other reads. Write lock scope is minimized. No deadlock potential. Background eviction thread doesn't hold locks during cleanup.

**Scoring Method:** `weighted_components`
**Max Points:** 14

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `rwlock_usage` | 30% | RwLock for read-heavy workloads, not Mutex | 1.0 if RwLock with concurrent reads, 0.5 if Mutex, 0.0 if no sync |
| `lock_granularity` | 35% | Lock held for minimum duration, no lock in I/O paths | 1.0 if fine-grained locking, 0.5 if coarse, 0.0 if lock held across operations |
| `deadlock_freedom` | 35% | No potential for deadlock (single lock order, no nested locks) | 1.0 if provably deadlock-free, 0.5 if likely safe, 0.0 if nested locks possible |

### Pass Examples

- let value = { let guard = self.inner.read().unwrap(); guard.get(&key).cloned() }; // read lock released before return

### Fail Examples

- Mutex::lock() held for entire get+update operation

---

## 3. rust_ttl_eviction

**Category:** functionality
**Description:** TTL expiry and background eviction are correctly implemented

**Pass Condition:** Per-entry TTL with configurable default. Background thread or task for periodic eviction. Lazy eviction on access (don't return expired entries). Background thread is cancellable (graceful shutdown).

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `per_entry_ttl` | 30% | Each entry has its own expiry timestamp | 1.0 if per-entry TTL, 0.5 if global only, 0.0 if no TTL |
| `background_eviction` | 30% | Periodic background sweep removes expired entries | 1.0 if background thread with configurable interval, 0.5 if lazy only, 0.0 if none |
| `lazy_check` | 20% | Get returns None for expired entries even before background sweep | 1.0 if lazy expiry on read, 0.0 if returns expired entries |
| `graceful_shutdown` | 20% | Background thread can be stopped cleanly | 1.0 if cancellation token / drop impl, 0.5 if join handle, 0.0 if leaked thread |

### Pass Examples

- spawn(move || { loop { sleep(interval); cache.evict_expired(); if shutdown.load(Relaxed) { break; } } })

### Fail Examples

- No TTL support, or global TTL with no per-entry override

---

## 4. rust_error_handling

**Category:** robustness
**Description:** Comprehensive error handling using Rust idioms (Result, custom errors)

**Pass Condition:** Custom error enum. No unwrap() in library code. Poisoned lock recovery. Memory bound enforcement. Errors are descriptive and actionable.

**Scoring Method:** `weighted_components`
**Max Points:** 8

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `error_types` | 35% | Custom error enum covering all failure modes | 1.0 if custom enum, 0.5 if string errors, 0.0 if panics |
| `no_unwrap` | 30% | No unwrap()/expect() in non-test code | 1.0 if all Results handled, 0.5 if few unwraps, 0.0 if unwrap-heavy |
| `poison_recovery` | 35% | Handles poisoned RwLock from panicked threads | 1.0 if recovers from poison, 0.5 if propagates, 0.0 if not addressed |

### Pass Examples

- match self.inner.read() { Ok(guard) => ..., Err(poisoned) => { let guard = poisoned.into_inner(); ... } }

### Fail Examples

- self.inner.read().unwrap() — panics on poisoned lock

---

## 5. rust_api_ergonomics

**Category:** usability
**Description:** API is idiomatic Rust with good documentation and generic type support

**Pass Condition:** Generic over K: Hash + Eq and V: Clone. Builder pattern for configuration. Implements standard traits (Debug, Drop). Doc comments with examples. Bounded memory via size_of or count.

**Scoring Method:** `weighted_components`
**Max Points:** 8

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `generics` | 30% | Generic over K and V with appropriate trait bounds | 1.0 if generic with bounds, 0.5 if specific types, 0.0 if String only |
| `builder` | 25% | Builder pattern for cache configuration | 1.0 if builder with fluent API, 0.5 if struct init, 0.0 if no config |
| `trait_impls` | 20% | Implements Debug, Drop (for cleanup), Send + Sync | % of appropriate traits implemented |
| `documentation` | 25% | Doc comments with usage examples on pub items | 1.0 if doc examples, 0.5 if basic docs, 0.0 if undocumented |

### Pass Examples

- LruCache::<String, Vec<u8>>::builder().capacity(1000).ttl(Duration::from_secs(300)).build()

### Fail Examples

- LruCache::new() with no configuration options, no docs

---
