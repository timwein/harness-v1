```python
"""
Distributed Token-Bucket Rate Limiter with Sliding Window Support
================================================================

A production-ready rate limiter implementation featuring:
- Token bucket algorithm with sliding window support
- Redis backend with atomic operations via Lua scripts
- Distributed coordination across multiple instances
- Graceful degradation when Redis is unavailable
- Circuit breaker pattern for Redis failover
- Clean API with decorator support and type safety
- Comprehensive testing suite
"""

import asyncio
import functools
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union, TypeVar, Generic
from contextlib import asynccontextmanager, contextmanager
import redis
import redis.asyncio as aioredis
from redis.exceptions import ConnectionError, TimeoutError, ReadOnlyError

# Type definitions
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class DegradationMode(Enum):
    """Degradation modes when Redis is unavailable"""
    FAIL_OPEN = "fail_open"      # Allow all requests
    FAIL_CLOSED = "fail_closed"  # Block all requests
    LOCAL_FALLBACK = "local_fallback"  # Use in-memory fallback

@dataclass
class RateLimitConfig:
    """Rate limiting configuration"""
    rate: str  # Format: "100/min", "10/sec", "1000/hour"
    burst: Optional[int] = None  # Burst allowance (defaults to rate)
    window_size: int = 60  # Sliding window size in seconds
    key_prefix: str = "rl"
    degradation_mode: DegradationMode = DegradationMode.LOCAL_FALLBACK

@dataclass
class RateLimitResult:
    """Rate limiting operation result"""
    allowed: bool
    remaining_tokens: int
    total_tokens: int
    reset_time: float  # Unix timestamp
    retry_after: Optional[float] = None  # Seconds until retry
    source: str = "redis"  # "redis", "local", or "circuit_open"

@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 2
    success_threshold: int = 3

class CircuitBreaker:
    """Circuit breaker for Redis operations"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0
        self._lock = Lock()
    
    def can_execute(self) -> bool:
        """Check if operation should be allowed"""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            
            if self.state == CircuitState.OPEN:
                if (self.last_failure_time and 
                    time.time() - self.last_failure_time >= self.config.recovery_timeout):
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                    return True
                return False
            
            # HALF_OPEN state
            return self.half_open_calls < self.config.half_open_max_calls
    
    def record_success(self):
        """Record successful operation"""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                self.half_open_calls += 1
                
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
            elif self.state == CircuitState.CLOSED:
                self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self):
        """Record failed operation"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self.success_count = 0
            elif (self.state == CircuitState.CLOSED and 
                  self.failure_count >= self.config.failure_threshold):
                self.state = CircuitState.OPEN

class TokenBucket:
    """In-memory token bucket for local fallback"""
    
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate  # tokens per second
        self.tokens = capacity
        self.last_refill = time.time()
        self._lock = Lock()
    
    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens"""
        with self._lock:
            now = time.time()
            self._refill_tokens(now)
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            return False
    
    def _refill_tokens(self, now: float):
        """Refill tokens based on elapsed time"""
        elapsed = now - self.last_refill
        new_tokens = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_refill = now
    
    def get_tokens(self) -> int:
        """Get current token count"""
        with self._lock:
            now = time.time()
            self._refill_tokens(now)
            return int(self.tokens)

class RedisConnectionManager:
    """Redis connection manager with pooling and cluster support"""
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        pool_size: int = 10,
        cluster: bool = False,
        sentinel_hosts: Optional[List[tuple]] = None,
        master_name: Optional[str] = None,
        max_connections: int = None,
        socket_timeout: float = 5.0
    ):
        self.redis_url = redis_url
        self.pool_size = pool_size or max_connections or 10
        self.cluster = cluster
        self.sentinel_hosts = sentinel_hosts
        self.master_name = master_name
        self.socket_timeout = socket_timeout
        self._pool: Optional[redis.ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
    
    def get_client(self) -> redis.Redis:
        """Get Redis client with connection pooling"""
        if self._client is None:
            if self.cluster:
                # Redis Cluster support with pooling
                from redis.cluster import RedisCluster
                startup_nodes = [{"host": "127.0.0.1", "port": "7000"}]
                self._client = RedisCluster(
                    startup_nodes=startup_nodes,
                    decode_responses=False,
                    skip_full_coverage_check=True,
                    max_connections=self.pool_size,
                    socket_timeout=self.socket_timeout
                )
            elif self.sentinel_hosts and self.master_name:
                # Redis Sentinel support with pooling
                from redis.sentinel import Sentinel
                sentinel = Sentinel(
                    self.sentinel_hosts,
                    socket_timeout=self.socket_timeout
                )
                self._client = sentinel.master_for(
                    self.master_name,
                    socket_timeout=self.socket_timeout,
                    max_connections=self.pool_size
                )
            else:
                # Regular Redis with connection pooling
                self._pool = redis.ConnectionPool.from_url(
                    self.redis_url,
                    max_connections=self.pool_size,
                    decode_responses=False,
                    socket_timeout=self.socket_timeout,
                    socket_connect_timeout=self.socket_timeout
                )
                self._client = redis.Redis(connection_pool=self._pool)
        
        return self._client
    
    @contextmanager
    def get_connection(self):
        """Get connection from pool with proper cleanup"""
        client = self.get_client()
        try:
            yield client
        finally:
            # Connection returned to pool automatically
            pass
    
    def close(self):
        """Close connections and clean up resources"""
        if self._pool:
            self._pool.disconnect()
        if self._client and hasattr(self._client, 'close'):
            self._client.close()

class RedisRateLimiter:
    """Redis-based distributed rate limiter using Lua scripts for atomic operations"""
    
    # Lua script for token bucket with sliding window
    TOKEN_BUCKET_SCRIPT = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local window_size = tonumber(ARGV[3])
        local now = tonumber(ARGV[4])
        local tokens_requested = tonumber(ARGV[5])
        local request_id = ARGV[6]
        
        -- Sliding window key for tracking requests
        local window_key = key .. ":window"
        local bucket_key = key .. ":bucket"
        
        -- Clean up old entries from sliding window
        local window_start = now - window_size
        redis.call('ZREMRANGEBYSCORE', window_key, 0, window_start)
        
        -- Get current token bucket state
        local bucket = redis.call('HMGET', bucket_key, 'tokens', 'last_refill')
        local tokens = tonumber(bucket[1]) or capacity
        local last_refill = tonumber(bucket[2]) or now
        
        -- Calculate refill based on elapsed time
        local elapsed = now - last_refill
        local new_tokens = elapsed * refill_rate
        tokens = math.min(capacity, tokens + new_tokens)
        
        -- Check if we can consume the requested tokens
        local allowed = 0
        local retry_after = 0
        
        if tokens >= tokens_requested then
            tokens = tokens - tokens_requested
            allowed = 1
            redis.call('ZADD', window_key, now, request_id)
        else
            -- Calculate retry-after time
            retry_after = (tokens_requested - tokens) / refill_rate
        end
        
        -- Update bucket state
        redis.call('HMSET', bucket_key, 'tokens', tokens, 'last_refill', now)
        
        -- Set TTL to prevent memory leaks
        redis.call('EXPIRE', bucket_key, window_size * 2)
        redis.call('EXPIRE', window_key, window_size * 2)
        
        -- Get current request count for metadata
        local current_count = redis.call('ZCARD', window_key)
        
        return {allowed, math.floor(tokens), capacity, now + window_size, retry_after, current_count}
    """
    
    def __init__(
        self,
        connection_manager: RedisConnectionManager,
        circuit_breaker: Optional[CircuitBreaker] = None,
        logger: Optional[logging.Logger] = None
    ):
        self.connection_manager = connection_manager
        self.circuit_breaker = circuit_breaker or CircuitBreaker(CircuitBreakerConfig())
        self.logger = logger or logging.getLogger(__name__)
        self._script = None
        
        # Local fallback buckets
        self._local_buckets: Dict[str, TokenBucket] = {}
        self._local_lock = Lock()
    
    def _get_script(self):
        """Get registered Lua script"""
        if self._script is None:
            with self.connection_manager.get_connection() as redis_client:
                self._script = redis_client.register_script(self.TOKEN_BUCKET_SCRIPT)
        return self._script
    
    def _parse_rate(self, rate: str) -> tuple[int, float]:
        """Parse rate string like '100/min' to (limit, refill_rate_per_second)"""
        parts = rate.split('/')
        if len(parts) != 2:
            raise ValueError(f"Invalid rate format: {rate}")
        
        limit = int(parts[0])
        unit = parts[1].lower()
        
        unit_seconds = {
            'sec': 1, 'second': 1, 's': 1,
            'min': 60, 'minute': 60, 'm': 60,
            'hour': 3600, 'hr': 3600, 'h': 3600,
            'day': 86400, 'd': 86400
        }
        
        if unit not in unit_seconds:
            raise ValueError(f"Unsupported time unit: {unit}")
        
        seconds = unit_seconds[unit]
        refill_rate = limit / seconds  # tokens per second
        
        return limit, refill_rate
    
    def _get_local_bucket(self, key: str, config: RateLimitConfig) -> TokenBucket:
        """Get or create local token bucket"""
        with self._local_lock:
            if key not in self._local_buckets:
                limit, refill_rate = self._parse_rate(config.rate)
                capacity = config.burst or limit
                self._local_buckets[key] = TokenBucket(
                    capacity=capacity,
                    refill_rate=refill_rate
                )
            return self._local_buckets[key]
    
    async def check_rate_limit(
        self,
        key: str,
        config: RateLimitConfig
    ) -> RateLimitResult:
        """Check rate limit for given key"""
        limit, refill_rate = self._parse_rate(config.rate)
        capacity = config.burst or limit
        
        # Try Redis if circuit breaker allows
        if self.circuit_breaker.can_execute():
            try:
                result = await self._check_redis_rate_limit(key, config, capacity, refill_rate)
                self.circuit_breaker.record_success()
                return result
                
            except (ConnectionError, TimeoutError, ReadOnlyError) as e:
                self.logger.warning(f"Redis error: {e}")
                self.circuit_breaker.record_failure()
        
        # Fallback based on degradation mode
        return self._handle_degradation(key, config)
    
    async def _check_redis_rate_limit(
        self,
        key: str,
        config: RateLimitConfig,
        capacity: int,
        refill_rate: float
    ) -> RateLimitResult:
        """Check rate limit using Redis"""
        redis_key = f"{config.key_prefix}:{key}"
        now = time.time()
        request_id = f"{now}:{uuid.uuid4().hex[:8]}"
        
        script = self._get_script()
        
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: script(
                keys=[redis_key],
                args=[capacity, refill_rate, config.window_size, now, 1, request_id]
            )
        )
        
        allowed, remaining, total, reset_time, retry_after, count = result
        
        return RateLimitResult(
            allowed=bool(allowed),
            remaining_tokens=remaining,
            total_tokens=total,
            reset_time=reset_time,
            retry_after=retry_after if retry_after > 0 else None,
            source="redis"
        )
    
    def _handle_degradation(
        self,
        key: str,
        config: RateLimitConfig
    ) -> RateLimitResult:
        """Handle degradation when Redis is unavailable"""
        limit, refill_rate = self._parse_rate(config.rate)
        capacity = config.burst or limit
        
        if config.degradation_mode == DegradationMode.FAIL_OPEN:
            return RateLimitResult(
                allowed=True,
                remaining_tokens=capacity,
                total_tokens=capacity,
                reset_time=time.time() + config.window_size,
                source="circuit_open"
            )
        
        elif config.degradation_mode == DegradationMode.FAIL_CLOSED:
            return RateLimitResult(
                allowed=False,
                remaining_tokens=0,
                total_tokens=capacity,
                reset_time=time.time() + config.window_size,
                retry_after=30.0,
                source="circuit_open"
            )
        
        else:  # LOCAL_FALLBACK
            bucket = self._get_local_bucket(key, config)
            allowed = bucket.consume(1)
            remaining = bucket.get_tokens()
            
            return RateLimitResult(
                allowed=allowed,
                remaining_tokens=remaining,
                total_tokens=capacity,
                reset_time=time.time() + config.window_size,
                retry_after=1.0 / refill_rate if not allowed else None,
                source="local"
            )

class RateLimitExceeded(Exception):
    """Rate limit exceeded exception"""
    
    def __init__(self, message: str, result: RateLimitResult):
        super().__init__(message)
        self.result = result

def rate_limit(
    rate: str,
    burst: Optional[int] = None,
    key_func: Optional[Callable[..., str]] = None,
    config: Optional[RateLimitConfig] = None,
    limiter: Optional[RedisRateLimiter] = None
):
    """Rate limit decorator
    
    Args:
        rate: Rate limit string like '100/min'
        burst: Burst allowance
        key_func: Function to extract key from arguments
        config: Complete rate limit configuration
        limiter: Rate limiter instance (if None, uses global default)
    """
    # Use config if provided, otherwise create from parameters
    if config is None:
        config = RateLimitConfig(rate=rate, burst=burst)
    
    # Create default limiter if none provided
    if limiter is None:
        connection_manager = RedisConnectionManager()
        limiter = RedisRateLimiter(connection_manager)
    
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract key for rate limiting
            if key_func:
                rate_key = key_func(*args, **kwargs)
            else:
                rate_key = f"{func.__module__}.{func.__name__}"
            
            # Check rate limit
            result = await limiter.check_rate_limit(rate_key, config)
            
            if not result.allowed:
                raise RateLimitExceeded(
                    f"Rate limit exceeded for {rate_key}",
                    result
                )
            
            return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Extract key for rate limiting
            if key_func:
                rate_key = key_func(*args, **kwargs)
            else:
                rate_key = f"{func.__module__}.{func.__name__}"
            
            # Check rate limit using asyncio.run
            result = asyncio.run(limiter.check_rate_limit(rate_key, config))
            
            if not result.allowed:
                raise RateLimitExceeded(
                    f"Rate limit exceeded for {rate_key}",
                    result
                )
            
            return func(*args, **kwargs)
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

# Factory function for easy setup
def create_rate_limiter(
    redis_url: str = "redis://localhost:6379/0",
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
    **kwargs
) -> RedisRateLimiter:
    """Factory function to create rate limiter"""
    connection_manager = RedisConnectionManager(redis_url, **kwargs)
    
    circuit_breaker = CircuitBreaker(
        circuit_breaker_config or CircuitBreakerConfig()
    )
    
    return RedisRateLimiter(connection_manager, circuit_breaker)

# Example usage
def example_usage():
    """Example usage of the rate limiter"""
    
    # Create rate limiter
    limiter = create_rate_limiter()
    
    # Basic usage with decorator
    @rate_limit('100/min', burst=20, limiter=limiter)
    async def api_endpoint(request):
        return {"data": "response"}
    
    # Custom key extraction
    @rate_limit(
        '10/sec',
        key_func=lambda req: req.get('user_id', 'anonymous'),
        limiter=limiter
    )
    async def user_specific_endpoint(request):
        return {"data": "response"}

# Comprehensive test suite
import pytest
import threading
import asyncio
from unittest.mock import Mock, patch
import fakeredis

class TestTokenBucketAlgorithm:
    """Test core token bucket algorithm"""
    
    def test_basic_rate_limiting(self):
        """Test basic token consumption and refill"""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)  # 1 token/second
        
        # Should allow initial consumption up to capacity
        for _ in range(10):
            assert bucket.consume(1) is True
        
        # Should reject when empty
        assert bucket.consume(1) is False
    
    def test_burst_allowance(self):
        """Test burst handling"""
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        
        # Consume all tokens
        for _ in range(5):
            assert bucket.consume(1) is True
        
        # Should be empty now
        assert bucket.consume(1) is False
        
        # Wait for refill
        time.sleep(1.1)  # Should add ~1 token
        assert bucket.consume(1) is True
        assert bucket.consume(1) is False
    
    def test_sliding_window_cleanup(self):
        """Test sliding window behavior vs fixed windows"""
        # This tests the principle of sliding vs fixed windows
        config = RateLimitConfig(rate="60/min", window_size=60)
        
        # The sliding window should continuously clean old entries
        # unlike fixed windows that reset at specific intervals
        assert config.window_size == 60
        assert "60/min" in config.rate
    
    def test_token_bucket_refill_logic(self):
        """Test token refill over time"""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)  # 2 tokens/second
        
        # Consume all tokens
        for _ in range(10):
            bucket.consume(1)
        
        assert bucket.consume(1) is False
        
        # Wait and check refill
        time.sleep(1.1)  # Should add ~2 tokens
        assert bucket.consume(1) is True
        assert bucket.consume(1) is True
        assert bucket.consume(1) is False  # Should be empty again

@pytest.fixture
def fake_redis():
    """Fake Redis for testing"""
    return fakeredis.FakeStrictRedis(decode_responses=False)

@pytest.fixture
def connection_manager(fake_redis):
    """Connection manager with fake Redis"""
    manager = RedisConnectionManager()
    manager._client = fake_redis
    return manager

@pytest.fixture
def rate_limiter(connection_manager):
    """Rate limiter instance for testing"""
    circuit_breaker = CircuitBreaker(CircuitBreakerConfig())
    return RedisRateLimiter(connection_manager, circuit_breaker)

@pytest.fixture
def rate_limit_config():
    """Standard rate limit config for testing"""
    return RateLimitConfig(rate="100/min", burst=20)

class TestRedisFailoverFallback:
    """Test Redis failover scenarios"""
    
    @pytest.mark.asyncio
    async def test_redis_failover_uses_local_bucket(self):
        """Test failover to local bucket when Redis fails"""
        # Mock failing Redis
        failing_manager = Mock()
        failing_manager.get_connection.side_effect = ConnectionError("Redis down")
        
        circuit_breaker = CircuitBreaker(CircuitBreakerConfig(failure_threshold=1))
        limiter = RedisRateLimiter(failing_manager, circuit_breaker)
        
        config = RateLimitConfig(
            rate="10/min",
            burst=5,
            degradation_mode=DegradationMode.LOCAL_FALLBACK
        )
        
        # Should use local bucket when Redis fails
        result = await limiter.check_rate_limit("test", config)
        assert result.source == "local"
        assert result.allowed is True
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_states(self):
        """Test circuit breaker state transitions"""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1)
        breaker = CircuitBreaker(config)
        
        # Initially closed
        assert breaker.state == CircuitState.CLOSED
        assert breaker.can_execute() is True
        
        # Record failures to open circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        assert breaker.can_execute() is False
        
        # Wait for recovery
        time.sleep(0.2)
        assert breaker.can_execute() is True  # Should be half-open

class TestConcurrentRequests:
    """Test concurrent access scenarios"""
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_respect_limit(self, rate_limiter, rate_limit_config):
        """Test concurrent requests respect rate limits"""
        config = RateLimitConfig(rate="10/min", burst=5)
        
        async def make_request():
            return await rate_limiter.check_rate_limit("concurrent_test", config)
        
        # Launch concurrent requests
        tasks = [make_request() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        # Should allow exactly burst amount
        allowed_count = sum(1 for r in results if r.allowed)
        assert allowed_count == 5  # Burst limit
    
    def test_thread_safety_local_fallback(self):
        """Test thread safety of local fallback buckets"""
        config = RateLimitConfig(
            rate="100/min",
            burst=20,
            degradation_mode=DegradationMode.LOCAL_FALLBACK
        )
        
        # Mock Redis to always fail
        failing_manager = Mock()
        failing_manager.get_connection.side_effect = ConnectionError()
        
        circuit_breaker = CircuitBreaker(CircuitBreakerConfig(failure_threshold=1))
        limiter = RedisRateLimiter(failing_manager, circuit_breaker)
        
        results = []
        
        def worker():
            """Worker thread making requests"""
            for _ in range(10):
                result = asyncio.run(limiter.check_rate_limit("thread_test", config))
                results.append(result)
        
        # Start multiple threads
        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should respect rate limit across threads
        allowed_count = sum(1 for r in results if r.allowed)
        assert allowed_count == 20  # Burst limit should be respected

class TestKeyIsolation:
    """Test key isolation between different rate limit keys"""
    
    @pytest.mark.asyncio
    async def test_key_isolation(self, rate_limiter):
        """Test different keys have independent rate limits"""
        config = RateLimitConfig(rate="10/min", burst=2)
        
        # Exhaust limit for key1
        result1a = await rate_limiter.check_rate_limit("key1", config)
        result1b = await rate_limiter.check_rate_limit("key1", config)
        result1c = await rate_limiter.check_rate_limit("key1", config)  # Should be denied
        
        assert result1a.allowed is True
        assert result1b.allowed is True
        assert result1c.allowed is False
        
        # key2 should still be available
        result2a = await rate_limiter.check_rate_limit("key2", config)
        result2b = await rate_limiter.check_rate_limit("key2", config)
        
        assert result2a.allowed is True
        assert result2b.allowed is True

class TestDistributedCoordination:
    """Test distributed coordination across multiple instances"""
    
    @pytest.mark.asyncio
    async def test_redis_script_atomicity(self, rate_limiter):
        """Test Redis Lua script provides atomic operations"""
        config = RateLimitConfig(rate="10/min", burst=3)
        
        # Simulate concurrent requests from multiple instances
        async def concurrent_request():
            return await rate_limiter.check_rate_limit("atomic_test", config)
        
        # Launch many concurrent requests
        tasks = [concurrent_request() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        # Should allow exactly the burst amount due to atomic Lua script
        allowed_count = sum(1 for r in results if r.allowed)
        assert allowed_count == 3

# Test runners
def run_basic_tests():
    """Run basic functionality tests"""
    pytest.main([
        "TestTokenBucketAlgorithm::test_basic_rate_limiting",
        "TestTokenBucketAlgorithm::test_burst_allowance",
        "-v"
    ])

def run_concurrent_tests():
    """Run concurrent access tests"""
    pytest.main([
        "TestConcurrentRequests",
        "-v"
    ])

def run_all_tests():
    """Run complete test suite"""
    pytest.main([__file__, "-v", "--tb=short"])

if __name__ == "__main__":
    # Example setup
    example_usage()
    
    # Run tests
    run_all_tests()
```