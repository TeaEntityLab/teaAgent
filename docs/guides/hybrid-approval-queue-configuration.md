# Hybrid Approval Queue Configuration Guide

## Overview

The hybrid approval queue combines file-based persistence with optional Redis caching to provide a resilient, scalable approval coordination system. This guide covers configuration options, monitoring, and operational best practices.

## Architecture

The hybrid queue uses a dual-write strategy:

- **Write Strategy:** Writes to both backends with configurable primary/secondary ordering
- **Read Strategy:** Reads from file (faster) with Redis fallback
- **Sync Strategy:** Periodic synchronization between backends with dynamic interval adjustment
- **Fallback:** Automatic fallback to secondary backend if primary fails

## Configuration

### Environment Variables

#### Backend Selection

```bash
# Use hybrid backend (file + Redis)
export TEAAGENT_APPROVAL_COORDINATION_BACKEND=hybrid

# Use file-based backend (default)
export TEAAGENT_APPROVAL_COORDINATION_BACKEND=file

# Use remote HTTP backend
export TEAAGENT_APPROVAL_COORDINATION_BACKEND=remote
```

#### Redis Configuration

```bash
# Redis connection
export TEAAGENT_REDIS_HOST=localhost
export TEAAGENT_REDIS_PORT=6379
export TEAAGENT_REDIS_PASSWORD=<password>
export TEAAGENT_REDIS_SSL=false

# Hybrid mode strategy
export TEAAGENT_REDIS_PRIMARY=true          # Redis as primary for writes
export TEAAGENT_HYBRID_SYNC_INTERVAL=60     # Base sync interval (seconds)
export TEAAGENT_HYBRID_FALLBACK=true        # Enable fallback to secondary
```

#### Circuit Breaker Configuration

```bash
# Enable circuit breaker for Redis calls
export TEAAGENT_HYBRID_CIRCUIT_BREAKER=true

# Circuit breaker thresholds
export TEAAGENT_CIRCUIT_BREAKER_FAILURE_THRESHOLD=5  # Failures before opening
export TEAAGENT_CIRCUIT_BREAKER_TIMEOUT_SECONDS=60    # Duration to stay open
export TEAAGENT_CIRCUIT_BREAKER_SUCCESS_THRESHOLD=2   # Successes to close
```

#### Dynamic Sync Configuration

```bash
# Enable dynamic sync interval adjustment
export TEAAGENT_HYBRID_DYNAMIC_SYNC=true

# Sync interval bounds
export TEAAGENT_HYBRID_MIN_SYNC_INTERVAL=10   # Minimum sync interval (seconds)
export TEAAGENT_HYBRID_MAX_SYNC_INTERVAL=300  # Maximum sync interval (seconds)
```

#### Advanced Features Configuration

```bash
# Request compression for large payloads
export TEAAGENT_HYBRID_COMPRESSION=true
export TEAAGENT_HYBRID_COMPRESSION_THRESHOLD=1024  # Bytes

# Request deduplication
export TEAAGENT_HYBRID_DEDUPLICATION=true
export TEAAGENT_HYBRID_DEDUPLICATION_WINDOW=300  # Seconds

# TTL/Auto-expiration
export TEAAGENT_HYBRID_TTL=true
export TEAAGENT_HYBRID_DEFAULT_TTL=3600  # Seconds

# Priority queue support
export TEAAGENT_HYBRID_PRIORITY=true

# Health check endpoint
export TEAAGENT_HYBRID_HEALTH_CHECK=true

# Rate limiting per subagent
export TEAAGENT_HYBRID_RATE_LIMITING=true
export TEAAGENT_HYBRID_RATE_LIMIT_REQUESTS_PER_MINUTE=60

# Audit trail
export TEAAGENT_HYBRID_AUDIT_TRAIL=true

# Request archival
export TEAAGENT_HYBRID_ARCHIVAL=true
export TEAAGENT_HYBRID_ARCHIVAL_AGE_DAYS=30
```

#### Security Configuration

```bash
# HMAC signing for approval queue files
export TEAAGENT_APPROVAL_HMAC_KEY=<secret-key>
```

### Programmatic Configuration

```python
from pathlib import Path
from teaagent.coordination.approval_hybrid_backend import (
    HybridApprovalCoordinationBackend,
)
from teaagent.subagents._approval_queue_redis_store import (
    RedisApprovalQueueConfig,
)
from teaagent.subagents._circuit_breaker import CircuitBreakerConfig

# Redis configuration
redis_config = RedisApprovalQueueConfig(
    host='localhost',
    port=6379,
    password=None,
    ssl=False,
)

# Circuit breaker configuration
circuit_breaker_config = CircuitBreakerConfig(
    failure_threshold=5,
    timeout_seconds=60,
    success_threshold=2,
)

# Create hybrid backend
backend = HybridApprovalCoordinationBackend(
    workspace_root=Path('/path/to/workspace'),
    hmac_secret='your-hmac-secret',
    redis_config=redis_config,
    redis_primary=True,
    sync_interval_seconds=60,
    enable_fallback=True,
    enable_circuit_breaker=True,
    circuit_breaker_config=circuit_breaker_config,
    enable_dynamic_sync=True,
)
```

## Features

### 1. Circuit Breaker Pattern

The circuit breaker prevents cascading failures by blocking calls to Redis after a threshold of failures is reached.

**States:**
- **CLOSED:** Normal operation
- **OPEN:** Blocking calls to Redis
- **HALF_OPEN:** Testing if Redis has recovered

**Configuration:**
- `failure_threshold`: Number of failures before opening (default: 5)
- `timeout_seconds`: Duration to stay open before trying again (default: 60)
- `success_threshold`: Number of successes to close from half-open (default: 2)

**Monitoring:**
```python
stats = backend.get_circuit_breaker_stats()
print(f"Circuit state: {stats['state']}")
print(f"Failures: {stats['failures']}")
print(f"Successes: {stats['successes']}")
```

### 2. Metrics and Monitoring

The hybrid queue collects comprehensive metrics for all operations.

**Metrics Collected:**
- Operation counts (save, get, update, sync, etc.)
- Success/failure rates
- Latency (min, max, average)
- Request lifecycle metrics (pending, approved, denied, timeout)
- Circuit breaker statistics
- Redis availability status
- Sync error counts

**Accessing Metrics:**
```python
metrics = backend.get_metrics()
print(f"Backend type: {metrics['backend_type']}")
print(f"Uptime: {metrics['uptime_seconds']}s")
print(f"Redis available: {metrics['redis_available']}")
print(f"Sync errors: {metrics['sync_errors']}")

# Operation-specific metrics
for op_name, op_metrics in metrics['operation_metrics'].items():
    print(f"{op_name}:")
    print(f"  Count: {op_metrics['count']}")
    print(f"  Success rate: {op_metrics['success_rate']:.2%}")
    print(f"  Avg latency: {op_metrics['avg_latency_ms']:.2f}ms")
```

**Global Metrics Collector:**
```python
from teaagent.subagents._approval_queue_metrics import get_metrics_collector

collector = get_metrics_collector()
all_metrics = collector.get_metrics()  # Get all backend metrics
```

### 3. Dynamic Sync Interval

The sync interval automatically adjusts based on system load to optimize performance.

**Load Factors:**
- Very fast operations (<10ms): 2x faster sync
- Fast operations (<50ms): 1.5x faster sync
- Normal operations (<100ms): Normal sync
- Slow operations (<500ms): 0.5x sync speed
- Very slow operations (>500ms): 0.25x sync speed

**Configuration:**
- `enable_dynamic_sync`: Enable/disable dynamic adjustment (default: true)
- `min_sync_interval_seconds`: Minimum sync interval (default: 10s)
- `max_sync_interval_seconds`: Maximum sync interval (default: 300s)

**Manual Sync Control:**
```python
# Check if sync should be performed
if backend._store.should_sync():
    result = backend.sync_to_file(parent_run_id)
    backend._store.record_sync()
```

### 4. Automatic Cleanup of Orphaned Requests

The system automatically cleans up orphaned requests and expired queues.

**Cleanup Actions:**
- Marks timed-out pending requests as TIMEOUT
- Deletes expired resolved queues (no pending requests, old)
- Removes orphaned parent runs

**Configuration:**
- `max_age_seconds`: Maximum age for resolved requests before cleanup (default: 3600s)
- `timeout_seconds`: Timeout for pending requests (default: 180s)

**Running Cleanup:**
```python
cleanup_report = backend.cleanup_orphaned_requests(
    max_age_seconds=3600,
    timeout_seconds=180,
)
print(f"Timed out requests: {cleanup_report['timed_out_requests']}")
print(f"Expired resolved requests: {cleanup_report['expired_resolved_requests']}")
print(f"Orphaned parent runs: {cleanup_report['orphaned_parent_runs']}")
print(f"Errors: {cleanup_report['errors']}")
```

### 5. Request Compression

Large request payloads can be automatically compressed to save storage space.

**Configuration:**
- `enable_compression`: Enable/disable compression (default: false)
- `compression_threshold_bytes`: Minimum size to trigger compression (default: 1024 bytes)

**Benefits:**
- Reduced disk usage for large payloads
- Faster sync operations for compressed data
- Transparent decompression on read

### 6. Request Deduplication

Prevents duplicate requests from being processed within a time window.

**Configuration:**
- `enable_deduplication`: Enable/disable deduplication (default: true)
- `deduplication_window_seconds`: Time window for duplicate detection (default: 300s)

**How It Works:**
- Computes hash based on subagent_id, tool_name, tool_arguments, permission_mode, and isolation
- Skips saving if a duplicate hash exists within the window
- Automatically cleans up old hashes

### 7. TTL/Auto-Expiration

Requests automatically expire after a configurable time-to-live.

**Configuration:**
- `enable_ttl`: Enable/disable TTL (default: true)
- `default_ttl_seconds`: Default TTL for requests (default: 3600s)

**Behavior:**
- Expired requests return None when retrieved
- Cleanup job removes expired requests
- Useful for temporary approval workflows

### 8. Priority Queue Support

Requests can be prioritized for processing order.

**Configuration:**
- `enable_priority`: Enable/disable priority queue (default: false)

**Usage:**
```python
# Set priority for a request
backend.set_request_priority('parent-1', 'req-123', priority=10)

# Get pending requests sorted by priority
pending = backend.get_pending_requests_by_priority('parent-1')
# Returns list sorted by priority (highest first)
```

### 9. Health Check Endpoint

Monitor the health of all queue components.

**Configuration:**
- `enable_health_check`: Enable/disable health check (default: true)

**Usage:**
```python
health = backend.health_check()
print(f"Overall status: {health['status']}")
print(f"File backend: {health['components']['file']}")
print(f"Redis backend: {health['components']['redis']}")
print(f"Circuit breaker: {health['components']['circuit_breaker']}")
print(f"Metrics: {health['components']['metrics']}")
```

**Health Status:**
- `healthy`: All components operational
- `degraded`: Some components unavailable but system functional
- `error`: Critical failures

### 10. Request Validation

Requests are validated against a schema before saving.

**Validation Checks:**
- Required fields (request_id, subagent_id, tool_name, permission_mode)
- Tool arguments must be a dictionary
- Isolation must be valid (shared, sandbox, isolated)
- Permission mode must be valid (workspace-read, workspace-write, network, system)
- Timeout seconds must be non-negative

**Usage:**
```python
is_valid, errors = backend.validate_request(request)
if not is_valid:
    print(f"Validation errors: {errors}")
```

### 11. Rate Limiting

Prevent subagents from overwhelming the system with too many requests.

**Configuration:**
- `enable_rate_limiting`: Enable/disable rate limiting (default: false)
- `rate_limit_requests_per_minute`: Max requests per subagent per minute (default: 60)

**Behavior:**
- Tracks request timestamps per subagent
- Rejects requests exceeding the limit
- Automatically cleans up old timestamps

### 12. Request Cancellation

Cancel pending requests before they are processed.

**Usage:**
```python
success = backend.cancel_request('parent-1', 'req-123', 'User cancelled')
if success:
    print('Request cancelled successfully')
```

**Constraints:**
- Only pending requests can be cancelled
- Approved/denied/cancelled requests cannot be cancelled

### 13. Request Search and Filtering

Search and filter requests by various criteria.

**Usage:**
```python
# Search by subagent
results = backend.search_requests('parent-1', subagent_id='subagent-1')

# Search by tool name
results = backend.search_requests('parent-1', tool_name='write_file')

# Search by status
results = backend.search_requests('parent-1', status='pending')

# Combine filters
results = backend.search_requests(
    'parent-1',
    subagent_id='subagent-1',
    tool_name='write_file',
    status='pending',
    limit=50,
)
```

### 14. Request Export/Import

Export and import requests for backup or migration.

**Usage:**
```python
# Export requests
exported_data = backend.export_requests('parent-1', format='json')

# Import requests
imported_count = backend.import_requests('parent-2', exported_data, format='json')
print(f'Imported {imported_count} requests')
```

**Supported Formats:**
- JSON (default)

### 15. Audit Trail

Track all operations on requests for compliance and debugging.

**Configuration:**
- `enable_audit_trail`: Enable/disable audit trail (default: true)

**Usage:**
```python
# Get all audit entries
audit = backend.get_audit_trail()

# Filter by parent run
audit = backend.get_audit_trail(parent_run_id='parent-1')

# Filter by request
audit = backend.get_audit_trail(request_id='req-123')

# Limit results
audit = backend.get_audit_trail(limit=50)
```

**Audit Entry Fields:**
- timestamp
- action (save_request, cancel_request, etc.)
- parent_run_id
- request_id
- details (action-specific data)

### 16. Request Archival

Automatically archive old requests to reduce active queue size.

**Configuration:**
- `enable_archival`: Enable/disable archival (default: false)
- `archival_age_days`: Age before archival (default: 30 days)

**Usage:**
```python
report = backend.archive_old_requests(max_age_days=30)
print(f'Archived {report["archived"]} requests')
print(f'Errors: {report["errors"]}')
```

**Behavior:**
- Moves old requests to separate storage
- Removes from active queue
- Preserves data for later retrieval

## Operational Best Practices

### 1. Monitoring

**Key Metrics to Monitor:**
- Redis availability status
- Circuit breaker state
- Operation success rates
- Average latency
- Sync error count
- Orphaned request count

**Alert Thresholds:**
- Redis availability < 95%
- Circuit breaker state = OPEN
- Operation success rate < 99%
- Average latency > 100ms
- Sync errors > 10/hour

### 2. Configuration Tuning

**High-Load Scenarios:**
- Enable Redis as primary for writes
- Reduce sync interval (30-60s)
- Enable dynamic sync with lower bounds
- Increase circuit breaker failure threshold

**Low-Load Scenarios:**
- Use file as primary for writes
- Increase sync interval (120-300s)
- Disable dynamic sync if load is predictable
- Lower circuit breaker timeout

**Development/Testing:**
- Use file-only backend
- Disable circuit breaker
- Disable metrics collection
- Set long sync intervals

### 3. Failure Handling

**Redis Failure:**
- Circuit breaker opens after threshold failures
- Automatic fallback to file backend
- Half-open state tests recovery
- Manual reset available via `circuit_breaker.reset()`

**File Failure:**
- Automatic fallback to Redis
- Error logging for debugging
- Dual-write ensures at least one backend succeeds

**Sync Failures:**
- Logged with error details
- Does not block operations
- Retry on next sync cycle

### 4. Security

**HMAC Signing:**
- Enable for production deployments
- Use strong random secret
- Rotate secrets periodically
- Store secret in secure environment variable

**Redis Security:**
- Use SSL in production
- Set strong password
- Use Redis ACLs if available
- Network isolation (VPC, firewall)

## Troubleshooting

### Circuit Breaker Stays Open

**Symptoms:** All Redis calls are blocked, circuit state = OPEN

**Solutions:**
1. Check Redis connectivity: `redis-cli ping`
2. Check Redis logs for errors
3. Verify Redis configuration
4. Manually reset: `backend._store._circuit_breaker.reset()`
5. Adjust timeout threshold if needed

### High Sync Errors

**Symptoms:** Sync error count increasing

**Solutions:**
1. Check Redis availability
2. Check disk space for file backend
3. Verify file permissions
4. Check network connectivity
5. Review logs for specific errors

### Orphaned Requests Accumulating

**Symptoms:** Queue files not being cleaned up

**Solutions:**
1. Run manual cleanup: `backend.cleanup_orphaned_requests()`
2. Adjust `max_age_seconds` threshold
3. Check for stuck parent processes
4. Verify cleanup job is running
5. Review cleanup logs

### Performance Degradation

**Symptoms:** High latency, slow operations

**Solutions:**
1. Check metrics for bottlenecks
2. Verify Redis performance (latency, memory)
3. Check disk I/O for file backend
4. Adjust sync interval based on load
5. Consider Redis cluster for high load

## API Reference

### HybridApprovalCoordinationBackend

**Methods:**
- `load_snapshot(parent_run_id)` - Load queue snapshot
- `save(parent_run_id, requests, batches)` - Save queue state
- `update_request_status(...)` - Update request status
- `list_parent_run_ids()` - List all parent runs
- `exists(parent_run_id)` - Check if queue exists
- `prune_stale(max_age_seconds)` - Prune old queues
- `sync_to_file(parent_run_id)` - Sync Redis → File
- `sync_to_redis(parent_run_id)` - Sync File → Redis
- `validate_consistency(parent_run_id)` - Check backend consistency
- `get_circuit_breaker_stats()` - Get circuit breaker stats
- `get_metrics()` - Get comprehensive metrics
- `cleanup_orphaned_requests(...)` - Clean up orphaned requests

**Properties:**
- `backend_id` - Backend identifier ('hybrid')
- `redis_available` - Redis availability status
- `file_store` - File store instance
- `redis_store` - Redis store instance

### HybridApprovalQueueStore

**Methods:**
- `save_request(parent_run_id, request)` - Save request
- `get_request(parent_run_id, request_id)` - Get request
- `update_request_status(...)` - Update status
- `get_pending_requests(parent_run_id)` - Get pending requests
- `save_batch(parent_run_id, batch)` - Save batch
- `get_batch(parent_run_id, batch_id)` - Get batch
- `sync_to_file(parent_run_id)` - Sync to file
- `sync_to_redis(parent_run_id)` - Sync to Redis
- `validate_consistency(parent_run_id)` - Validate consistency
- `list_parent_run_ids()` - List parent runs
- `exists(parent_run_id)` - Check existence
- `delete_parent_run(parent_run_id)` - Delete queue
- `get_metrics()` - Get metrics
- `should_sync()` - Check if sync needed
- `record_sync()` - Record sync completion
- `cleanup_orphaned_requests(...)` - Clean up orphans

**Properties:**
- `redis_available` - Redis availability
- `file_store` - File store
- `redis_store` - Redis store

## Migration Guide

### From File-Only to Hybrid

1. **Set up Redis:**
   ```bash
   # Install Redis
   sudo apt-get install redis-server  # Ubuntu/Debian
   brew install redis                  # macOS

   # Start Redis
   redis-server
   ```

2. **Configure environment:**
   ```bash
   export TEAAGENT_APPROVAL_COORDINATION_BACKEND=hybrid
   export TEAAGENT_REDIS_HOST=localhost
   export TEAAGENT_REDIS_PORT=6379
   ```

3. **Enable gradually:**
   - Start with `redis_primary=false` (file primary, Redis backup)
   - Monitor metrics and circuit breaker state
   - Switch to `redis_primary=true` when confident

4. **Validate consistency:**
   ```python
   report = backend.validate_consistency(parent_run_id)
   print(f"Consistency rate: {report['consistency_rate']:.2%}")
   ```

### From Hybrid to File-Only

1. **Sync to file:**
   ```python
   result = backend.sync_to_file(parent_run_id)
   print(f"Synced {result['synced']} items")
   ```

2. **Change backend:**
   ```bash
   export TEAAGENT_APPROVAL_COORDINATION_BACKEND=file
   ```

3. **Verify data:**
   - Check file queue directory
   - Verify request counts match
   - Test approval operations

## Performance Benchmarks

Expected performance characteristics:

| Operation | File Backend | Redis Backend | Hybrid (File Read) |
|-----------|--------------|----------------|-------------------|
| Save Request | 5-10ms | 2-5ms | 5-10ms |
| Get Request | 1-2ms | 1-2ms | 1-2ms |
| Update Status | 5-10ms | 2-5ms | 5-10ms |
| Get Pending | 2-5ms | 1-3ms | 2-5ms |
| Sync (100 items) | N/A | 50-100ms | 50-100ms |

**Notes:**
- Hybrid read performance matches file backend (file-first strategy)
- Write performance depends on primary backend selection
- Sync overhead is amortized over time
- Circuit breaker adds minimal overhead (<1ms)

## Support

For issues or questions:
- Check logs for detailed error messages
- Review metrics for performance insights
- Consult troubleshooting section
- Open GitHub issue with logs and metrics
