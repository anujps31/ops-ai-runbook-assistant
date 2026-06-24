# Memory Leak Runbook

## Problem
An application gradually consumes more memory over time, eventually leading to OOMKilled termination. Memory is not released after use, indicating a leak in the application code or dependent libraries.

## Symptoms
1. Memory usage increases continuously even under constant load
2. Heap size grows over days/weeks of operation
3. Garbage collection happens more frequently and takes longer
4. Full garbage collections cannot reclaim significant memory
5. Java/Python processes report increasingly high memory footprint
6. Pod eventually terminates with OOMKilled after days/weeks
7. Application performance degrades over time proportional to memory growth
8. Restarting pod immediately frees all memory (temporarily)
9. Memory growth visible in long-term monitoring graphs
10. No correlation with traffic or load changes

## Impact
- **Availability**: Pod eventually crashes due to OOM
- **Stability**: Application requires frequent restarts to function
- **Predictability**: Unpredictable crash timing impacts SLA
- **Resource waste**: Other workloads can't use memory held by leak
- **Operations**: Requires manual intervention or auto-restart

## Possible Root Causes
1. **Unclosed resources**: Connections, file handles, streams not closed
2. **Collection growth**: List/dict/set grows without clearing
3. **Static references**: Static class variables hold references preventing GC
4. **Circular references**: Objects reference each other, preventing GC
5. **Cache without eviction**: Cache grows unbounded without TTL/size limit
6. **Event listener leaks**: Event listeners registered but never unregistered
7. **Timer/interval leak**: setInterval/setTimeout not cleared
8. **Database connection leak**: Connection pool exhausted, connections not returned
9. **Third-party library**: Dependency library contains memory leak
10. **Weak reference misuse**: Accidentally strong references instead of weak

## Investigation Steps

### Step 1: Confirm Memory Leak Pattern
```bash
# Get pod memory usage over time (requires monitoring system)
# Query Prometheus: container_memory_rss_bytes over last 7 days

# Alternatively, stream memory usage in real-time
kubectl exec <pod-name> -n <namespace> -- watch -n 5 'cat /proc/meminfo | head -5'

# Get memory stats from container
kubectl exec <pod-name> -n <namespace> -- cat /proc/self/status | grep -E "VmRSS|VmSize|VmPeak"

# Monitor memory growth rate
kubectl exec <pod-name> -n <namespace> -- python -c \
  "import psutil, time; p = psutil.Process(1); 
  while True: print(f'{time.time()} {p.memory_info().rss / 1024**2:.2f}MB'); time.sleep(60)"
```

### Step 2: Take Heap Dumps for Analysis
```bash
# For Java applications - take heap dump
kubectl exec <pod-name> -n <namespace> -- jmap -dump:live,format=b,file=heap.bin <pid>

# Copy heap dump to local machine for analysis
kubectl cp <namespace>/<pod-name>:heap.bin heap.bin

# Analyze with Eclipse MAT or similar tool
# Download from: https://www.eclipse.org/mat/

# For Python applications - get memory snapshot
kubectl exec <pod-name> -n <namespace> -- python -c \
  "import gc, tracemalloc; tracemalloc.start(); \
  gc.collect(); snapshot = tracemalloc.take_snapshot(); \
  top_stats = snapshot.statistics('lineno'); \
  [print(stat) for stat in top_stats[:10]]"

# For Go applications - use pprof
kubectl exec <pod-name> -n <namespace> -- curl http://localhost:6060/debug/pprof/heap > heap.prof
```

### Step 3: Identify Culprit Objects
```bash
# For Java - get object count by type
kubectl exec <pod-name> -n <namespace> -- jmap -histo <pid> | head -30

# Get top growing objects
kubectl exec <pod-name> -n <namespace> -- jmap -histo:live <pid> | sort -k2 -rn | head -20

# Check for retained objects
kubectl exec <pod-name> -n <namespace> -- jcmd <pid> GC.heap_info

# For Python - get reference count
kubectl exec <pod-name> -n <namespace> -- python -c \
  "import sys, gc; 
  gc.collect(); 
  objects = gc.get_objects(); 
  print(f'Total objects: {len(objects)}'); 
  from collections import Counter; 
  types = Counter(type(o).__name__ for o in objects); 
  print(types.most_common(10))"
```

### Step 4: Check Application Logs
```bash
# Look for connection/resource related errors
kubectl logs <pod-name> -n <namespace> | grep -i "connection\|resource\|leak" | tail -50

# Check for warning logs about unclosed resources
kubectl logs <pod-name> -n <namespace> | grep -i "unclosed\|not closed" | tail -20

# Look for repeated error patterns suggesting accumulation
kubectl logs <pod-name> -n <namespace> | tail -1000 | sort | uniq -c | sort -rn | head -20
```

### Step 5: Monitor Garbage Collection Behavior
```bash
# For Java - enable GC logging
kubectl set env deployment/<deployment-name> \
  JVM_OPTS="-Xmx1g -XX:+PrintGCDetails -XX:+PrintGCDateStamps -Xloggc:/tmp/gc.log" \
  -n <namespace>

# Get GC logs from container
kubectl exec <pod-name> -n <namespace> -- tail -100 /tmp/gc.log

# Analyze GC time vs memory freed
# Long GC times with little memory freed = likely leak

# For Python - enable gc debug
kubectl exec <pod-name> -n <namespace> -- python -c \
  "import gc; gc.enable(); gc.set_debug(gc.DEBUG_SAVEALL); gc.collect(); \
  print(f'Uncollectable objects: {len(gc.garbage)}')"
```

### Step 6: Profile Memory Allocation
```bash
# For Java - use JProfiler or YourKit profiler
# Configure profiler in deployment
kubectl set env deployment/<deployment-name> \
  JVM_OPTS="-agentpath:/opt/jprofiler/bin/libjprofilerti.so" \
  -n <namespace>

# For Python - use memory_profiler decorator
# Add to suspected function:
# @profile
# def my_function():
#     ...

# Run with profiler
kubectl exec <pod-name> -n <namespace> -- python -m memory_profiler script.py

# For general allocation tracking
kubectl exec <pod-name> -n <namespace> -- python -c \
  "import tracemalloc; tracemalloc.start(); \
  [your_function_call()]; \
  snapshot = tracemalloc.take_snapshot(); \
  top_stats = snapshot.statistics('lineno'); \
  print('[ Top 10 ]'); \
  for stat in top_stats[:10]: print(stat)"
```

### Step 7: Check Cache Configuration
```bash
# Review application configuration for cache settings
kubectl get configmap <app-config> -n <namespace> -o yaml | grep -i "cache\|ttl\|evict"

# Check if cache has size/TTL limits
grep -r "cache\|ttl" <application-code>

# Example: Redis cache without eviction policy
kubectl exec <redis-pod> -n <namespace> -- redis-cli CONFIG GET maxmemory-policy

# Example: Java cache growth
kubectl exec <pod-name> -n <namespace> -- jmap -histo <pid> | grep -i "cache\|map\|list"
```

### Step 8: Examine File Descriptors and Connections
```bash
# Check open file descriptors
kubectl exec <pod-name> -n <namespace> -- cat /proc/<pid>/limits | grep "open files"

# Count current open files
kubectl exec <pod-name> -n <namespace> -- ls -1 /proc/<pid>/fd | wc -l

# Check for leaked connections
kubectl exec <pod-name> -n <namespace> -- netstat -an | grep ESTABLISHED | wc -l

# Monitor connection count over time
kubectl exec <pod-name> -n <namespace> -- watch -n 10 'netstat -an | grep ESTABLISHED | wc -l'

# Check database connection pool status
kubectl logs <pod-name> -n <namespace> | grep -i "connection\|pool" | tail -30
```

### Step 9: Review Recent Code Changes
```bash
# Look at recent commits
git log --oneline -20

# Identify memory-related changes
git log -p -- <file> | grep -A5 -B5 "list\|dict\|cache\|connection"

# Compare current version with previous
git diff HEAD~1 -- <suspicious-file>

# Check for common leak patterns
grep -r "new \|malloc\|alloc" <code-path> | grep -v "free\|delete\|release\|close"
```

### Step 10: Test with Different Heap Size
```bash
# For Java - increase heap to see if leak still occurs
kubectl set env deployment/<deployment-name> \
  JVM_OPTS="-Xmx4g" \
  -n <namespace>

# Redeploy and monitor how long before memory fills up
kubectl rollout restart deployment/<deployment-name> -n <namespace>

# Measure time to OOM as proxy for leak rate
# If previously 1 week, now ~4 weeks = leak rate identified
```

## Resolution Steps

### For Unclosed Connections: Add Resource Management
```bash
# Before (leak):
def get_data():
    conn = db.connect()
    data = conn.query("SELECT * FROM table")
    return data  # Connection never closed!

# After (fixed):
def get_data():
    with db.connect() as conn:
        data = conn.query("SELECT * FROM table")
        return data  # Connection automatically closed

# Rebuild and deploy
kubectl rollout restart deployment/<deployment-name> -n <namespace>
```

### For Growing Collections: Add Size/TTL Limits
```bash
# Before (leak):
cache = {}
def cache_result(key, value):
    cache[key] = value  # Grows forever

# After (fixed):
from functools import lru_cache
@lru_cache(maxsize=1000)
def cache_result(key, value):
    return value  # Auto-evicts LRU entries

# Or use explicit eviction:
cache = {}
MAX_CACHE_SIZE = 1000
def cache_result(key, value):
    if len(cache) >= MAX_CACHE_SIZE:
        # Remove oldest entry
        oldest = min(cache, key=lambda k: cache[k]['timestamp'])
        del cache[oldest]
    cache[key] = value
```

### For Static Reference Leaks: Use Weak References
```bash
# Before (leak):
class EventManager:
    _listeners = []  # Static list holding strong references
    @staticmethod
    def register(listener):
        EventManager._listeners.append(listener)

# After (fixed):
import weakref
class EventManager:
    _listeners = []
    @staticmethod
    def register(listener):
        EventManager._listeners.append(weakref.ref(listener))
```

### For External Library Leak: Update or Work Around
```bash
# Check for known issue in library
npm audit
pip check
bundle audit

# Update to patched version
npm install <library>@latest

# Or implement workaround (e.g., periodic restart)
# Add CronJob to restart pod periodically
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: CronJob
metadata:
  name: pod-restart
spec:
  schedule: "0 * * * *"  # Every hour
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: restart
            image: bitnami/kubectl
            command: 
            - kubectl
            - rollout
            - restart
            - deployment/<deployment-name>
EOF
```

### Deploy Fix and Monitor
```bash
# Build and push new image with fix
docker build -t registry/app:fixed .
docker push registry/app:fixed

# Rollout new version
kubectl set image deployment/<deployment-name> \
  <container-name>=registry/app:fixed \
  -n <namespace>

# Monitor memory usage over several days
kubectl top pod <pod-name> -n <namespace> --watch
```

## Validation
```bash
# Memory should stabilize at consistent level
kubectl top pod <pod-name> -n <namespace> --containers

# No memory growth over 7+ days
# Query: rate(container_memory_rss_bytes[7d]) should be ~0

# Pod should not OOMKilled
kubectl get pod <pod-name> -n <namespace> | grep -i "restart\|oomkilled"

# GC behavior should be consistent
# Full GC should reclaim most memory each cycle
```

## Prevention
- Use memory profilers during development and staging
- Add automated heap dump analysis in CI/CD
- Implement circuit breakers for resource allocation
- Use resource pooling with proper cleanup
- Implement cache eviction policies (LRU, TTL)
- Regular dependency security/stability audits
- Stress test applications to identify leaks early
- Monitor memory trends in staging before production
- Add memory alerts at 70%, 80%, 90% thresholds
- Document resource cleanup procedures in code

## Severity
**P2** - Eventually causes service outage, requires investigation and code fix.

## Escalation Matrix
| Duration | Action |
|----------|--------|
| 1 day | Start profiling, identify leak source |
| 3 days | Identify specific code causing leak |
| 7 days | Code fix must be ready |
| 14 days | If still leaking, escalate to dev team |
