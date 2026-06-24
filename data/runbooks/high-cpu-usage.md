# High CPU Usage Runbook

## Problem
A pod or node exhibits sustained high CPU usage (>80%), causing slow application response times, increased latency, and potential service degradation. High CPU may indicate inefficient code, resource contention, or workload imbalance.

## Symptoms
1. CPU utilization consistently above 80% in kubectl top
2. Application response times increase significantly
3. Request latency percentiles (p95, p99) spike
4. Thread count or process count increases abnormally
5. Load average on node exceeds number of CPU cores
6. Kubernetes metrics show CPU throttling
7. Applications timeout due to slow processing
8. CPU-bound process identified via top command
9. No recent code deployment but CPU usage increased
10. Multiple processes competing for CPU on same node

## Impact
- **User experience**: Requests timeout, application sluggish
- **Throughput**: Lower requests per second handled
- **Reliability**: Service may become unavailable under sustained load
- **Auto-scaling**: Triggers unnecessary pod scaling
- **Cost**: Higher CPU consumed = higher cloud costs

## Possible Root Causes
1. **Inefficient algorithm**: O(n²) instead of O(n) complexity
2. **Infinite loop**: Code stuck in tight loop without breaks
3. **Synchronous blocking**: Blocking I/O in request handler
4. **Lock contention**: Multiple threads competing for same lock
5. **Garbage collection**: Pause times from Java/Python GC
6. **Regex complexity**: Complex regex on large strings (ReDoS)
7. **Unoptimized query**: Slow database query consuming CPU
8. **Memory pressure**: Swapping causing CPU overhead
9. **Noisy neighbor**: Other pod on node using high CPU
10. **Library bug**: Dependency library has inefficient code path

## Investigation Steps

### Step 1: Identify High CPU Pod/Process
```bash
# Get CPU usage by pod
kubectl top pod -n <namespace> --sort-by=cpu | head -20

# Get specific pod CPU usage
kubectl top pod <pod-name> -n <namespace> --containers

# Get CPU usage by node
kubectl top nodes --sort-by=cpu

# Get detailed node CPU info
kubectl describe node <node-name> | grep -A 10 "Allocated resources"
```

### Step 2: Check CPU Throttling
```bash
# Get CPU metrics with throttling info
kubectl exec <pod-name> -n <namespace> -- cat /sys/fs/cgroup/cpu/cpu.stat

# Get CPU throttling metrics from Prometheus
# Query: rate(container_cpu_cfs_throttled_seconds_total[5m])

# Check if CPU limit is too low relative to usage
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.containers[0].resources.limits.cpu}'

# Check CPU requests
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.containers[0].resources.requests.cpu}'
```

### Step 3: Profile CPU Usage Inside Container
```bash
# SSH to node or use exec to identify hot process
kubectl exec -it <pod-name> -n <namespace> -- top -b -n 1

# Show processes by CPU usage
kubectl exec -it <pod-name> -n <namespace> -- ps aux --sort=-%cpu | head -20

# Get thread count for process
kubectl exec <pod-name> -n <namespace> -- cat /proc/<pid>/status | grep Threads

# Use CPU profiler (Python example)
kubectl exec <pod-name> -n <namespace> -- python -m cProfile -s cumulative <script>

# Use Java Flight Recorder (Java example)
kubectl exec <pod-name> -n <namespace> -- jcmd <pid> JFR.start
kubectl exec <pod-name> -n <namespace> -- jcmd <pid> JFR.dump filename=flight-record.jfr
```

### Step 4: Check Application Logs for Errors
```bash
# Get application logs looking for errors
kubectl logs <pod-name> -n <namespace> | grep -i "error\|exception\|busy" | tail -50

# Check for spinning/tight loops
kubectl logs <pod-name> -n <namespace> | tail -100 | grep -c "same message"

# Check for queue buildup
kubectl logs <pod-name> -n <namespace> | grep -i "queue\|processing" | tail -20
```

### Step 5: Check Database Performance
```bash
# If application queries database, check query performance
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e "SHOW PROCESSLIST;"

# Check slow query log
kubectl exec <db-pod> -n <namespace> -- tail -f /var/log/mysql/slow.log

# Get query statistics
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e "SELECT * FROM performance_schema.events_statements_summary_by_digest ORDER BY SUM_TIMER_WAIT DESC LIMIT 10\\G"

# Check table locks
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e "SHOW OPEN TABLES WHERE In_use > 0;"
```

### Step 6: Check for Lock Contention
```bash
# For Java applications using synchronized blocks
kubectl exec <pod-name> -n <namespace> -- jstack <pid> | grep -i "locked\|waiting" | head -20

# For Python applications
kubectl exec <pod-name> -n <namespace> -- python -c "import sys; import threading; print(threading.enumerate())"

# Check Go goroutines
kubectl exec <pod-name> -n <namespace> -- curl http://localhost:6060/debug/pprof/goroutine
```

### Step 7: Monitor CPU Usage Over Time
```bash
# Stream pod CPU usage
kubectl top pod <pod-name> -n <namespace> --containers --watch

# Watch node CPU from metrics-server
kubectl get --raw /apis/metrics.k8s.io/v1beta1/nodes/<node-name> | jq '.usage.cpu'

# Get CPU history from Prometheus
# Query: rate(container_cpu_usage_seconds_total[5m])
```

### Step 8: Check for Noisy Neighbor
```bash
# Get all pods on same node
kubectl get pods --all-namespaces -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\t"}{.spec.nodeName}{"\n"}{end}' | grep <node-name>

# Get CPU usage of all pods on node
kubectl top pod --all-namespaces --field-selector spec.nodeName=<node-name> --sort-by=cpu

# Identify which pod is consuming most CPU
kubectl top pod --all-namespaces | sort -k3 -rn | head -10
```

### Step 9: Check Recent Deployments/Changes
```bash
# Check deployment rollout history
kubectl rollout history deployment/<deployment-name> -n <namespace>

# See what changed in recent deployment
kubectl rollout history deployment/<deployment-name> -n <namespace> --revision=<revision>

# Check git diff for recent changes
git log --oneline -10
git diff HEAD~1 HEAD -- <file>

# Check if this is reproducible with previous version
kubectl rollout undo deployment/<deployment-name> -n <namespace> --to-revision=<previous>
```

### Step 10: Review Code for Hot Paths
```bash
# Use flamegraph to visualize CPU usage
# (Requires profiling tool in container)
kubectl exec <pod-name> -n <namespace> -- perf record -g sleep 30
kubectl exec <pod-name> -n <namespace> -- perf report

# Or use commercial APM tool
# New Relic, DataDog, Dynatrace profiling

# Check for known performance issues in dependencies
npm audit
pip check
bundle audit
```

## Resolution Steps

### If Code Has Infinite Loop: Emergency Fix
```bash
# Identify problematic code path from profiler
# Add circuit breaker or max iteration limit:

# Before:
# while True:
#     process_item()

# After:
# max_iterations = 1000
# iteration = 0
# while iteration < max_iterations:
#     process_item()
#     iteration += 1

# Deploy fix
kubectl set image deployment/<deployment-name> \
  <container-name>=<new-image>:<tag-with-fix> \
  -n <namespace>
```

### If Slow Query: Optimize Database
```bash
# Add index to frequently queried column
kubectl exec <db-pod> -n <namespace> -- mysql -u root <db> -e \
  "CREATE INDEX idx_column ON table(column);"

# Review and rewrite slow query
# Replace: SELECT * FROM large_table WHERE condition
# With: SELECT needed_columns FROM large_table WHERE optimized_condition LIMIT 1000

# Add query timeout
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SET GLOBAL max_statement_time=5000;"
```

### If Lock Contention: Use Non-Blocking Synchronization
```bash
# Replace synchronized blocks with ReentrantReadWriteLock
# Before:
# synchronized(sharedResource) {
#     readData();
# }

# After:
# readLock.lock();
# try {
#     readData();
# } finally {
#     readLock.unlock();
# }

# Rebuild and deploy
kubectl rollout restart deployment/<deployment-name> -n <namespace>
```

### If Garbage Collection Pauses: Tune GC
```bash
# For Java: use low-latency garbage collector
export JVM_OPTS="-XX:+UseZGC -XX:+UnlockExperimentalVMOptions"

# Or use incremental GC
export JVM_OPTS="-XX:+UseG1GC -XX:MaxGCPauseMillis=200"

# Set in deployment
kubectl set env deployment/<deployment-name> \
  JVM_OPTS="-XX:+UseZGC" \
  -n <namespace>

# Restart pods to pick up new JVM options
kubectl rollout restart deployment/<deployment-name> -n <namespace>
```

### If High Load: Scale Horizontally
```bash
# Increase replica count
kubectl scale deployment/<deployment-name> --replicas=5 -n <namespace>

# Or configure Horizontal Pod Autoscaler
kubectl autoscale deployment/<deployment-name> \
  --min=2 --max=10 --cpu-percent=70 \
  -n <namespace>

# Or update existing HPA
kubectl patch hpa <hpa-name> -n <namespace> -p \
  '{"spec":{"targetCPUUtilizationPercentage":70}}'
```

## Validation
```bash
# CPU usage should drop after fix
kubectl top pod <pod-name> -n <namespace> --watch

# Application response time should improve
# Monitor from load testing tool

# Request p95/p99 latencies should decrease
# Query from metrics/APM tool

# No throttling should occur
kubectl exec <pod-name> -n <namespace> -- cat /sys/fs/cgroup/cpu/cpu.stat | grep throttled
```

## Prevention
- Implement continuous CPU profiling in staging environment
- Load test before production deployment
- Set appropriate CPU limits and requests
- Monitor CPU usage trends with alerting
- Code review focusing on algorithmic complexity
- Use static analysis tools to detect performance issues
- Implement rate limiting to prevent overload
- Cache expensive computations
- Use async/non-blocking I/O patterns
- Regular APM profiling in production

## Severity
**P2** - Degrades user experience and service performance, requires investigation and optimization.

## Escalation Matrix
| Duration | Action |
|----------|--------|
| < 5 min | Check top pods/processes |
| 5-15 min | Profile CPU usage, identify hot path |
| 15-30 min | Implement code or database fix |
| 30-60 min | Deploy fix or scale up |
| > 60 min | Escalate to architecture team |
