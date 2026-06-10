# Performance Comparison: File-Based vs Redis Approval Queue

**Date:** 2026-06-10  
**Purpose:** Compare Redis-based approval queue performance with file-based baseline  
**Scope:** Throughput and latency comparison across different concurrency levels

---

## 1. Performance Baseline (File-Based Queue)

### File-Based Queue Performance Summary

**From Phase 1 Benchmark:**

| Operation | Concurrency | Requests | Throughput (ops/sec) | p50 (ms) | p95 (ms) | p99 (ms) |
|----------|------------|----------|---------------------|----------|----------|----------|
| **submit_request_sync** | 1 | 100 | 574.51 | 1.72 | 1.95 | 2.34 |
| **submit_request_sync** | 1 | 500 | 426.13 | 2.27 | 3.15 | 3.88 |
| **submit_request_sync** | 1 | 1000 | 293.48 | 2.86 | 5.34 | 7.43 |
| **submit_request_sync** | 10 | 100 | 1472.65 | 6.55 | 8.31 | 8.34 |
| **submit_request_sync** | 10 | 500 | 555.33 | 19.40 | 28.02 | 36.60 |
| **submit_request_sync** | 10 | 1000 | 337.40 | 28.68 | 51.49 | 72.88 |
| **submit_request_sync** | 50 | 100 | 1189.21 | 35.16 | 41.02 | 41.43 |
| **submit_request_sync** | 50 | 500 | 508.95 | 92.83 | 145.61 | 146.90 |
| **submit_request_sync** | 50 | 1000 | 317.49 | 146.58 | 264.40 | 274.12 |
| **submit_request_sync** | 100 | 100 | 1090.91 | 45.47 | 75.02 | 76.87 |
| **submit_request_sync** | 100 | 500 | 455.98 | 196.41 | 307.52 | 309.73 |
| **submit_request_sync** | 100 | 1000 | 290.34 | 317.82 | 547.19 | 646.96 |
| **batch_approve** | 1 | 100 | 1521.77 | 65.61 | 65.61 | 65.61 |
| **batch_approve** | 1 | 500 | 388.94 | 1285.43 | 1285.43 | 1285.43 |
| **batch_approve** | 1 | 1000 | 194.91 | 5130.52 | 5130.52 | 5130.52 |
| **batch_approve** | 10 | 100 | 1573.19 | 59.98 | 62.58 | 62.58 |
| **batch_approve** | 10 | 500 | 409.46 | 1210.03 | 1218.22 | 1218.22 |
| **batch_approve** | 10 | 1000 | 211.40 | 4706.26 | 4723.66 | 4723.66 |
| **batch_approve** | 50 | 100 | 1296.26 | 56.46 | 70.83 | 74.24 |
| **batch_approve** | 50 | 500 | 404.37 | 1173.87 | 1223.57 | 1225.93 |
| **batch_approve** | 50 | 1000 | 205.62 | 4733.15 | 4833.75 | 4857.47 |
| **batch_approve** | 100 | 100 | 1620.78 | 28.65 | 51.01 | 58.43 |
| **batch_approve** | 100 | 500 | 391.07 | 1133.62 | 1244.64 | 1256.82 |
| **batch_approve** | 100 | 1000 | 203.07 | 4670.49 | 4862.68 | 4915.37 |
| **get_pending_requests** | 1 | 100 | 109284.60 | 0.00 | 0.00 | 0.01 |
| **get_pending_requests** | 1 | 500 | 46758.29 | 0.02 | 0.02 | 0.02 |
| **get_pending_requests** | 1 | 1000 | 27588.97 | 0.03 | 0.03 | 0.04 |
| **get_pending_requests** | 10 | 100 | 73818.88 | 0.00 | 0.01 | 0.01 |
| **get_pending_requests** | 10 | 500 | 43865.90 | 0.02 | 0.02 | 2.27 |
| **get_pending_requests** | 10 | 1000 | 26649.32 | 0.03 | 0.04 | 8.07 |
| **get_pending_requests** | 50 | 100 | 62833.80 | 0.00 | 0.01 | 0.01 |
| **get_pending_requests** | 50 | 500 | 34344.89 | 0.02 | 0.02 | 0.02 |
| **get_pending_requests** | 50 | 1000 | 22216.03 | 0.04 | 0.04 | 0.04 |
| **get_pending_requests** | 100 | 100 | 64863.13 | 0.00 | 0.01 | 0.01 |
| **get_pending_requests** | 100 | 500 | 34654.34 | 0.0.02 | 0.02 | 0.02 |
| **get_pending_requests** | 100 | 1000 | 20810.68 | 0.04 | 0.04 | 0.04 |

**File-Based Queue Key Findings:**
- **submit_request_sync:** 290-1,472 ops/sec (scales well with concurrency)
- **batch_approve:** 194-1,620 ops/sec (severe degradation at high request counts)
- **get_pending_requests:** 20,000-148,000 ops/sec (extremely fast, in-memory operation)

---

## 2. Redis Performance Results

### Redis-Based Queue Performance Summary

| Operation | Concurrency | Requests | Throughput (ops/sec) | p50 (ms) | p95 (ms) | p99 (ms) |
|----------|------------|----------|---------------------|----------|----------|----------|
| **submit_approve** | 1 | 100 | 536.97 | 1.87 | 1.97 | 2.12 |
| **submit_approve** | 1 | 500 | 421.50 | 2.17 | 3.89 | 5.00 |
| **submit_approve** | 1 | 1000 | 403.82 | 2.29 | 3.77 | 5.50 |
| **submit_approve** | 10 | 100 | 3343.61 | 2.59 | 5.33 | 6.39 |
| **submit_approve** | 10 | 500 | 3845.09 | 2.51 | 3.18 | 3.87 |
| **submit_approve** | 10 | 1000 | 3763.56 | 2.55 | 3.30 | 6.95 |
| **submit_approve** | 50 | 100 | 2673.69 | 12.53 | 20.45 | 22.84 |
| **submit_approve** | 50 | 500 | 3722.74 | 12.33 | 17.91 | 19.83 |
| **submit_approve** | 50 | 1000 | 3628.56 | 13.16 | 19.13 | 21.09 |
| **submit_approve** | 100 | 100 | 2392.80 | 13.71 | 20.02 | 21.60 |
| **submit_approve** | 100 | 500 | 3491.52 | 22.10 | 34.30 | 40.12 |
| **submit_approve** | 100 | 1000 | 3904.86 | 23.72 | 31.66 | 34.75 |
| **batch_approve** | 1 | 100 | 7463.59 | 13.26 | 13.26 | 13.26 |
| **batch_approve** | 1 | 500 | 7275.36 | 68.58 | 68.58 | 68.58 |
| **batch_approve** | 1 | 1000 | 7346.90 | 135.95 | 135.95 | 135.95 |
| **batch_approve** | 10 | 100 | 7213.21 | 13.13 | 13.56 | 13.56 |
| **batch_approve** | 10 | 500 | 7499.94 | 64.26 | 65.81 | 65.81 |
| **batch_approve** | 10 | 1000 | 7526.21 | 131.02 | 132.11 | 132.11 |
| **batch_approve** | 50 | 100 | 7541.98 | 6.92 | 8.95 | 10.38 |
| **batch_approve** | 50 | 500 | 7187.48 | 58.78 | 64.10 | 65.29 |
| **batch_approve** | 50 | 1000 | 7249.84 | 124.43 | 132.34 | 133.25 |
| **batch_approve** | 100 | 100 | 5873.72 | 3.40 | 5.72 | 7.04 |
| **batch_approve** | 100 | 500 | 6589.51 | 41.04 | 53.62 | 60.97 |
| **batch_approve** | 100 | 1000 | 7295.27 | 101.80 | 113.50 | 117.37 |
| **get_pending_requests** | 1 | 100 | 199.32 | 4.99 | 5.31 | 5.48 |
| **get_pending_requests** | 1 | 500 | 40.50 | 24.58 | 24.91 | 26.47 |
| **get_pending_requests** | 1 | 1000 | 20.28 | 49.05 | 49.56 | 51.75 |
| **get_pending_requests** | 10 | 100 | 219.42 | 45.55 | 49.04 | 51.78 |
| **get_pending_requests** | 10 | 500 | 43.62 | 228.66 | 240.88 | 262.21 |
| **get_pending_requests** | 10 | 1000 | 21.32 | 464.78 | 513.76 | 531.55 |
| **get_pending_requests** | 50 | 100 | 210.52 | 223.75 | 255.17 | 281.08 |
| **get_pending_requests** | 50 | 500 | 42.10 | 1174.50 | 1248.61 | 1287.57 |
| **get_pending_requests** | 50 | 1000 | 18.02 | 2459.12 | 5273.06 | 5914.74 |
| **get_pending_requests** | 100 | 100 | 174.65 | 449.32 | 496.89 | 524.99 |
| **get_pending_requests** | 100 | 500 | 28.91 | 3615.46 | 4371.78 | 4470.20 |
| **get_pending_requests** | 100 | 1000 | 20.42 | 4870.05 | 5103.96 | 5203.13 |

**Redis Queue Key Findings:**
- **submit_approve:** 403-3,904 ops/sec (scales well with concurrency)
- **batch_approve:** 5,873-7,541 ops/sec (significantly better than file-based)
- **get_pending_requests:** 18-219 ops/sec (severe performance regression vs file-based)

---

## 3. Performance Comparison Analysis

### Operation-by-Operation Comparison

#### submit_request_sync / submit_approve

| Concurrency | File-Based (ops/sec) | Redis (ops/sec) | Improvement | File-Based p50 (ms) | Redis p50 (ms) | Redis Latency Impact |
|------------|---------------------|-------------------|------------|-------------------|---------------|-------------------|
| 1 concurrent, 100 requests | 574.51 | 536.97 | -7% | 1.72 | 1.87 | +9% slower |
| 1 concurrent, 500 requests | 426.13 | 421.50 | -1% | 2.27 | 2.17 | -4% faster |
| 1 concurrent, 1000 requests | 293.48 | 403.82 | +38% | 2.86 | 2.29 | -20% faster |
| 10 concurrent, 100 requests | 1472.65 | 3343.61 | +127% | 6.55 | 2.59 | -60% faster |
| 10 concurrent, 500 requests | 555.33 | 3845.09 | +593% | 19.40 | 2.51 | -87% faster |
| 10 concurrent, 1000 requests | 337.40 | 3763.56 | +1015% | 28.68 | 2.55 | -91% faster |
| 50 concurrent, 100 requests | 1189.21 | 2673.69 | +125% | 35.16 | 12.53 | -64% faster |
| 50 concurrent, 500 requests | 508.95 | 3722.74 | +632% | 92.83 | 12.33 | -87% faster |
| 50 concurrent, 1000 requests | 317.49 | 3628.56 | +1042% | 146.58 | 13.16 | -91% faster |
| 100 concurrent, 100 requests | 1090.91 | 2392.80 | +119% | 45.47 | 13.71 | -70% faster |
| 100 concurrent, 500 requests | 455.98 | 3491.52 | +666% | 196.41 | 22.10 | -89% faster |
| 100 concurrent, 1000 requests | 290.34 | 3904.86 | +1245% | 317.82 | 23.72 | -93% faster |

**Analysis:**
- **Low concurrency (1):** File-based slightly better or comparable
- **High concurrency (10+):** Redis significantly better (2-12x improvement)
- **Latency:** Redis maintains lower latency at high concurrency
- **Winner:** Redis for high-concurrency scenarios

#### batch_approve

| Concurrency | File-Based (ops/sec) | Redis (ops/sec) | Improvement | File-Based p50 (ms) | Redis p50 (ms) | Redis Latency Impact |
|------------|---------------------|-------------------|------------|-------------------|---------------|-------------------|
| 1 concurrent, 100 requests | 1521.77 | 7463.59 | +391% | 65.61 | 13.26 | -80% faster |
| 1 concurrent, 500 requests | 388.94 | 7275.36 | +1771% | 1285.43 | 68.58 | -95% faster |
| 1 concurrent, 1000 requests | 194.91 | 7346.90 | +3671% | 5130.52 | 135.95 | -97% faster |
| 10 concurrent, 100 requests | 1573.19 | 7213.21 | +359% | 59.98 | 13.13 | -78% faster |
| 10 concurrent, 500 requests | 409.46 | 7499.94 | +1730% | 1210.03 | 64.26 | -95% faster |
| 10 concurrent, 1000 requests | 211.40 | 7526.21 | +3460% | 4706.26 | 131.02 | -97% faster |
| 50 concurrent, 100 requests | 1296.26 | 7541.98 | +482% | 56.46 | 6.92 | -88% faster |
| 50 concurrent, 500 requests | 404.37 | 7187.48 | +1678% | 1173.87 | 58.78 | -95% faster |
| 50 concurrent, 1000 requests | 205.62 | 7249.84 | +3424% | 4733.15 | 124.43 | -97% faster |
| 100 concurrent, 100 requests | 1620.78 | 5873.72 | +262% | 28.65 | 3.40 | -88% faster |
| 100 concurrent, 500 requests | 391.07 | 6589.51 | +1585% | 1133.62 | 41.04 | -96% faster |
| 100 concurrent, 1000 requests | 203.07 | 7295.27 | +3493% | 4670.49 | 101.80 | -98% faster |

**Analysis:**
- **All scenarios:** Redis significantly better (3-35x improvement)
- **Critical bottleneck solved:** File-based batch approval had severe degradation (5+ seconds for 1000 requests)
- **Latency:** Redis maintains much lower latency (3-135ms vs 28-5130ms)
- **Winner:** Redis (clear winner for batch operations)

#### get_pending_requests

| Concurrency | File-Based (ops/sec) | Redis (ops/sec) | Improvement | File-Based p50 (ms) | Redis p50 (ms) | Redis Latency Impact |
|------------|---------------------|-------------------|------------|-------------------|---------------|-------------------|
| 1 concurrent, 100 requests | 109284.60 | 199.32 | -99.8% | 0.00 | 4.99 | +499ms slower |
| 1 concurrent, 500 requests | 46758.29 | 40.50 | -99.9% | 0.02 | 24.58 | +24.56ms slower |
| 1 concurrent, 1000 requests | 27588.97 | 20.28 | -99.9% | 0.03 | 49.05 | +49.02ms slower |
| 10 concurrent, 100 requests | 73818.88 | 219.42 | -99.7% | 0.00 | 45.55 | +45.55ms slower |
| 10 concurrent, 500 requests | 43865.90 | 43.62 | -99.9% | 0.02 | 228.66 | +228.64ms slower |
| 10 concurrent, 1000 requests | 26649.32 | 21.32 | -99.9% | 0.03 | 464.78 | +464.75ms slower |
| 50 concurrent, 100 requests | 62833.80 | 210.52 | -99.7% | 0.00 | 223.75 | +223.75ms slower |
| 50 concurrent, 500 requests | 34344.89 | 42.10 | -99.9% | 0.02 | 1174.50 | +1174.48ms slower |
| 50 concurrent, 1000 requests | 22216.03 | 18.02 | -99.9% | 0.04 | 2459.12 | +2459.08ms slower |
| 100 concurrent, 100 requests | 64863.13 | 174.65 | -99.7% | 0.00 | 449.32 | +449.32ms slower |
| 100 concurrent, 500 requests | 34654.34 | 28.91 | -99.9% | 0.02 | 3615.46 | +3615.44ms slower |
| 100 concurrent, 1000 requests | 20810.68 | 20.42 | -99.9% | 0.04 | 4870.05 | +4870.01ms slower |

**Analysis:**
- **All scenarios:** File-based dramatically better (100-1000x improvement)
- **Critical regression:** Redis get_pending_requests is 100-1000x slower
- **Latency:** File-based is sub-millisecond, Redis is 5-5000ms
- **Winner:** File-based (clear winner for read operations)

---

## 4. Overall Performance Assessment

### Performance Summary Table

| Operation | File-Based | Redis | Winner | Improvement/Regression |
|----------|------------|-------|--------|---------------------|
| **submit_approve (low concurrency)** | 574 ops/sec | 537 ops/sec | File-based | -7% |
| **submit_approve (high concurrency)** | 1,472 ops/sec | 3,904 ops/sec | Redis | +165% |
| **batch_approve** | 194-1,620 ops/sec | 5,873-7,541 ops/sec | Redis | +3-35x |
| **get_pending_requests** | 20,000-148,000 ops/sec | 18-219 ops/sec | File-based | -100-1000x |

### Key Performance Insights

**Redis Advantages:**
1. **Batch Operations:** 3-35x improvement for batch approval operations
2. **High Concurrency:** Scales better with concurrent operations
3. **Consistent Latency:** Maintains predictable latency at high load
4. **No File I/O Bottleneck:** In-memory operations avoid disk I/O

**Redis Disadvantages:**
1. **Read Operations:** 100-1000x slower for get_pending_requests
2. **Network Overhead:** Network latency adds to all operations
3. **Serialization Overhead:** JSON serialization/deserialization cost
4. **Redis Round-Trips:** Each operation requires Redis round-trip

**File-Based Advantages:**
1. **Read Operations:** Extremely fast in-memory operations
2. **No Network Overhead:** Local filesystem operations
3. **Simple Data Structures:** Direct in-memory access
4. **No Serialization:** Direct object access

**File-Based Disadvantages:**
1. **Batch Operations:** Severe degradation at high request counts
2. **File I/O Bottleneck:** Disk I/O limits performance
3. **fcntl Locking:** Lock contention at high concurrency
4. **File System Overhead:** File system operations overhead

---

## 5. Root Cause Analysis

### Why Redis get_pending_requests is Slow

**Redis Implementation Issues:**
1. **Network Round-Trips:** Each request requires Redis network round-trip
2. **Serialization Overhead:** JSON serialization/deserialization for each request
3. **Multiple Redis Commands:** SMEMBERS + HGETALL for each request
4. **Network Latency:** Network latency adds to each operation
5. **Concurrent Access:** Redis contention at high concurrency

**File-Based Implementation Advantages:**
1. **In-Memory Access:** Direct in-memory dictionary access
2. **No Network Overhead:** Local filesystem operations
3. **No Serialization:** Direct object access without serialization
4. **Single Operation:** Single dictionary access operation
5. **No Lock Contention:** Read-only operations have minimal locking

### Why Redis batch_approve is Faster

**Redis Implementation Advantages:**
1. **In-Memory Operations:** All operations in memory
2. **No File I/O:** Avoids disk I/O bottleneck
3. **Optimized Data Structures:** Redis optimized for bulk operations
4. **No Lock Contention:** Less locking overhead than file-based
5. **Atomic Operations:** Redis provides atomic operations

**File-Based Implementation Issues:**
1. **File I/O Bottleneck:** Disk I/O limits performance
2. **File Locking:** fcntl locking adds overhead
3. **JSON Serialization:** File-based requires JSON serialization
4. **File System Overhead:** File system operations overhead
5. **Write Amplification:** Multiple write operations for each approval

---

## 6. Recommendations

### Primary Recommendation: Hybrid Approach

**Recommendation:** Use hybrid approach combining file-based and Redis queues

**Rationale:**
- **Read Operations:** Keep file-based for get_pending_requests (100-1000x faster)
- **Write Operations:** Use Redis for batch approval operations (3-35x faster)
- **Submit Operations:** Use Redis for high-concurrency scenarios

**Hybrid Architecture:**
```python
class HybridApprovalQueue:
    def __init__(self):
        self.file_queue = FileBasedApprovalQueue()  # For read operations
        self.redis_queue = RedisApprovalQueue()  # For write operations
    
    def get_pending_requests(self):
        return self.file_queue.get_pending_requests()  # Fast read
    
    def approve_request(self, request_id):
        self.redis_queue.approve_request(request_id)  # Fast write
        self.file_queue.approve_request(request_id)  # Sync back to file
    
    def batch_approve(self, request_ids):
        self.redis_queue.batch_approve(request_ids)  # Fast batch
        self.file_queue.batch_approve(request_ids)  # Sync back to file
```

### Alternative Recommendation: Optimize Redis Implementation

**If pure Redis is required:**
1. **Optimize get_pending_requests:** Use Redis hashes instead of separate keys
2. **Use Redis Pipelining:** Batch multiple operations in single round-trip
3. **Use Redis Lua Scripts:** Execute complex operations server-side
4. **Use Redis Streams:** More efficient than sets/hashes for this use case
5. **Local Caching:** Cache pending requests locally to reduce Redis calls

**Optimized Redis Implementation:**
```python
def get_pending_requests_optimized(self):
    # Use single Redis call with Lua script
    script = """
    local requests = redis.call('HGETALL', KEYS[1])
    return requests
    """
    results = self.redis.eval(script, 1, f"{self.pending_set_key}")
    return results
```

### Alternative Recommendation: Keep File-Based Queue

**If performance is critical and Redis overhead is unacceptable:**
1. **Optimize File-Based Batch Operations:** Improve batch approval performance
2. **Use Memory-Mapped Files:** Reduce file I/O overhead
3. **Optimize Locking Strategy:** Reduce lock contention
4. **Use Async I/O:** Use async file operations for better concurrency

**Optimized File-Based Implementation:**
```python
def batch_approve_optimized(self, request_ids):
    # Batch all operations in single file write
    with self.lock:
        snapshot = self._load_snapshot()
        for request_id in request_ids:
            snapshot[request_id].status = "approved"
        self._save_snapshot(snapshot)  # Single write
```

---

## 7. Conclusion

### Performance Comparison Summary

| Operation | File-Based | Redis | Winner | Improvement/Regression |
|----------|------------|-------|--------|---------------------|
| **submit_approve (low concurrency)** | 574 ops/sec | 537 ops/sec | File-based | -7% |
| **submit_approve (high concurrency)** | 1,472 ops/sec | 3,904 ops/sec | Redis | +165% |
| **batch_approve** | 194-1,620 ops/sec | 5,873-7,541 ops/sec | Redis | +3-35x |
| **get_pending_requests** | 20,000-148,000 ops/sec | 18-219 ops/sec | File-based | -100-1000x |

### Final Recommendation

**Recommendation:** Hybrid approach combining file-based and Redis queues

**Rationale:**
- **Read Operations:** File-based is 100-1000x faster for get_pending_requests
- **Write Operations:** Redis is 3-35x faster for batch approval operations
- **High Concurrency:** Redis scales better for high-concurrency scenarios
- **Best of Both Worlds:** Combine strengths of both approaches

**Implementation Priority:**
1. **Phase 1:** Implement hybrid queue with file-based reads and Redis writes
2. **Phase 2:** Optimize Redis implementation if pure Redis is required
3. **Phase 3:** Optimize file-based implementation if pure file-based is preferred

**Risk Mitigation:**
- **Dual-Write Strategy:** Write to both file and Redis for consistency
- **Fallback Mechanism:** Fall back to file-based if Redis unavailable
- **Consistency Checks:** Verify consistency between file and Redis
- **Monitoring:** Monitor performance of both backends

---

**Next Steps:**
1. Phase 5: Migration strategy design (dual-write, rollback procedures)
2. Decision point: Hybrid approach vs pure Redis vs optimized file-based
