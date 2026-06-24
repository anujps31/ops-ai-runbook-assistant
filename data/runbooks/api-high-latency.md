# API High Latency Runbook

## Problem
API response times increase significantly (>1 second), causing timeout errors and poor user experience. Individual operations that should complete in milliseconds take seconds.

## Symptoms
1. API p99 latency > 5 seconds, p95 > 3 seconds
2. Timeout errors from clients
3. Request queues backing up
4. Specific endpoints slower than others
5. Latency spikes during certain times
6. Database query time increased
7. Network latency to dependencies increased
8. CPU or memory usage elevated
9. Garbage collection pauses visible
10. Connection pool utilization high

## Possible Root Causes
1. **Slow database queries**: Inefficient SQL, missing indexes
2. **Network latency**: High latency to dependencies
3. **Resource contention**: CPU/memory limited or shared
4. **GC pauses**: Java/Python garbage collection stutters
5. **Lock contention**: Synchronization bottlenecks
6. **Disk I/O**: Swapping or slow disk access
7. **Network saturation**: Bandwidth limit reached
8. **Third-party API slow**: Dependency slow to respond
9. **Connection pool exhaustion**: Waiting for available connection
10. **Cache miss cascades**: High cache miss rate causes load

## Investigation Steps

### Step 1: Get Latency Metrics
```bash
# Get API latency from monitoring system
# Query Prometheus: histogram_quantile(0.99, rate(http_request_duration_seconds[5m]))

# Get latency distribution
# p50, p95, p99 percentiles should show where tail latency is

# Check if latency correlated with other metrics
# CPU usage, memory usage, request rate

# Get latency by endpoint
# Query: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{endpoint="specific"}[5m]))

# Example with curl
curl http://localhost:8080/metrics | grep http_request_duration_seconds
```

### Step 2: Check Request Rate
```bash
# Get requests per second
# Query: rate(http_requests_total[1m])

# Check if latency increases with load
# Manual test: gradual increase in requests, monitor latency

# Get load on API servers
kubectl top pod <api-pod> -n <namespace>

# Check if specific pod is bottleneck
kubectl get pods -n <namespace> -l app=api -o wide

# Get request distribution across replicas
# Query: rate(http_requests_total[1m]) by (pod)
```

### Step 3: Profile Slow Endpoint
```bash
# Time a single request
time curl -v https://api.example.com/slow-endpoint

# Breakdown: DNS (ms), Connect (ms), TLS (ms), First byte (ms), Total (ms)
curl -w "@-" -o /dev/null -s https://api.example.com/endpoint <<'EOF'
    time_namelookup:  %{time_namelookup}\n
    time_connect:     %{time_connect}\n
    time_appconnect:  %{time_appconnect}\n
    time_pretransfer: %{time_pretransfer}\n
    time_redirect:    %{time_redirect}\n
    time_starttransfer: %{time_starttransfer}\n
    ----------
    time_total:       %{time_total}\n
EOF

# If starttransfer high = server processing slow
# If connect high = network latency
```

### Step 4: Check Database Performance
```bash
# Get slow queries
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT query_time, sql_text FROM mysql.slow_log ORDER BY query_time DESC LIMIT 20;"

# Check query execution plan
kubectl exec <db-pod> -n <namespace> -- mysql -u root <db> -e \
  "EXPLAIN ANALYZE SELECT ...;"

# Get table statistics
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT * FROM performance_schema.events_statements_summary_by_digest ORDER BY SUM_TIMER_WAIT DESC LIMIT 10\\G"

# Check for table locks
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e "SHOW OPEN TABLES WHERE In_use > 0;"
```

### Step 5: Check Network Latency
```bash
# Ping dependencies from pod
kubectl exec <api-pod> -n <namespace> -- ping -c 5 <dependency-host>

# Traceroute to identify path
kubectl exec <api-pod> -n <namespace> -- traceroute <dependency-host>

# Check network MTU
kubectl exec <api-pod> -n <namespace> -- ip link show | grep mtu

# Check for packet loss
# Run over time: for i in {1..100}; do ping -c 1 -W 1 <host>; done

# Monitor network bandwidth
kubectl top pod <api-pod> -n <namespace>
```

### Step 6: Check Resource Usage
```bash
# Get API pod resource usage over time
kubectl top pod <api-pod> -n <namespace> --containers

# Check CPU throttling
kubectl exec <api-pod> -n <namespace> -- cat /sys/fs/cgroup/cpu/cpu.stat

# Check memory usage
kubectl exec <api-pod> -n <namespace> -- cat /proc/self/status | grep -E "VmRSS|VmSize"

# Check if near limits
kubectl get pod <api-pod> -n <namespace> -o jsonpath='{.spec.containers[0].resources}'

# Monitor node resources
kubectl top node <node>
```

### Step 7: Profile Application
```bash
# For Java - use JProfiler or async-profiler
# Add to JVM: -javaagent:/path/to/async-profiler.jar=start,event=cpu,file=/tmp/profile.html

# For Python - use cProfile
kubectl exec <api-pod> -n <namespace> -- python -m cProfile -s cumulative <script>

# For Go - use pprof
# curl http://localhost:6060/debug/pprof/profile?seconds=30 > profile.prof

# For general - check hot paths
# What functions are called most frequently?
# Where is most time spent?
```

### Step 8: Check Garbage Collection
```bash
# For Java - get GC logs
kubectl logs <api-pod> -n <namespace> | grep "GC" | tail -20

# Check pause times
# Look for: "G1 Humongous Allocation" or "Full GC" messages

# Get GC statistics
kubectl exec <api-pod> -n <namespace> -- jstat -gcutil <pid> 1000 5

# If GC pauses high (>100ms) = GC issue
# Example output: 25% time in GC

# For Python - check GC collections
kubectl exec <api-pod> -n <namespace> -- python -c \
  "import gc; print(f'Collections: {gc.get_stats()}')"
```

### Step 9: Check Lock Contention
```bash
# For Java - get thread dump
kubectl exec <api-pod> -n <namespace> -- jstack <pid> | grep -A 5 "BLOCKED"

# Count blocked threads (should be low)
kubectl exec <api-pod> -n <namespace> -- jstack <pid> | grep -c "waiting to lock"

# For Python - get lock contention
# Use line_profiler or py-spy

# Check for synchronized blocks in code
grep -r "synchronized\|Lock\|Mutex" <source-code>
```

### Step 10: Check Cache Hit Rates
```bash
# Get cache statistics from monitoring
# Query: cache_hits / (cache_hits + cache_misses)

# If hit rate < 70% = cache ineffective

# Increase cache size if possible
kubectl set env deployment/<deployment> \
  CACHE_SIZE=10000 \
  -n <namespace>

# Clear stale cache
kubectl exec <cache-pod> -n <namespace> -- redis-cli FLUSHALL

# Monitor hit rate after change
# Should increase to >90%
```

## Resolution Steps

### For Slow Queries: Add Index
```bash
# Identify slow query
# Add index to frequently queried column
kubectl exec <db-pod> -n <namespace> -- mysql -u root <db> -e \
  "CREATE INDEX idx_column ON table(column);"

# Verify index helps
# Re-run EXPLAIN ANALYZE

# If still slow, optimize query or code
```

### For High GC Pauses: Tune JVM
```bash
# Use low-latency GC
kubectl set env deployment/<deployment> \
  JVM_OPTS="-XX:+UseZGC -XX:+UnlockExperimentalVMOptions" \
  -n <namespace>

# Or use G1GC with lower pause targets
kubectl set env deployment/<deployment> \
  JVM_OPTS="-XX:+UseG1GC -XX:MaxGCPauseMillis=200" \
  -n <namespace>

# Redeploy
kubectl rollout restart deployment/<deployment> -n <namespace>
```

### For Resource Constrained: Scale or Increase Limits
```bash
# Increase replicas for horizontal scaling
kubectl scale deployment/<deployment> --replicas=5 -n <namespace>

# Or increase per-pod resources
kubectl set resources deployment/<deployment> \
  -n <namespace> \
  --limits=cpu=2000m,memory=2Gi

# Redeploy
kubectl rollout restart deployment/<deployment> -n <namespace>
```

### For Network Latency: Optimize Calls
```bash
# Batch API calls
# Before: 100 individual requests
# After: 1 batched request with 100 items

# Implement request caching
# Cache response for 5 minutes
# Reduce redundant calls

# Use connection pooling
# Reuse HTTP connections

# Add timeout to prevent hanging
timeout = 5  # seconds
```

## Validation
```bash
# Latency should improve
# Query: histogram_quantile(0.99, rate(http_request_duration_seconds[5m]))

# p99 should be < 1 second after fix
# p95 should be < 500ms

# Request queue should decrease
# Error rate should drop

# Specific slow endpoint should respond faster
time curl https://api.example.com/endpoint
```

## Prevention
- Set latency SLOs (p99 < 1s, p95 < 500ms)
- Monitor latency percentiles continuously
- Load test before production
- Profile applications regularly
- Right-size database indexes
- Implement request caching
- Monitor slow queries automatically
- Alert on latency increase > 50%
- Document expected latencies per endpoint

## Severity
**P2** - Degrades user experience, requires optimization.

## Escalation Matrix
| p99 Latency | Action |
|-------------|--------|
| < 500ms | Good |
| 500ms - 1s | Monitor |
| 1-5s | Investigate root cause |
| > 5s | Page engineer, start optimization |
