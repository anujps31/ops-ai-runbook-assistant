# Pod OOMKilled Runbook

## Problem
A pod is terminated due to out-of-memory (OOM) condition. The Linux kernel OOMKiller forcefully terminates the process to prevent the entire node from becoming unresponsive. Pod repeatedly restarts with exit code 137 (SIGKILL signal).

## Symptoms
1. Pod terminates with exit code 137 (OOM signal)
2. LastState reason shows `OOMKilled`
3. Memory usage reaches container limit before termination
4. Pod restart loop with 137 exit codes
5. Node dmesg shows OOM killer messages: `Out of memory: Kill process`
6. Memory metrics show pod at exactly memory limit (e.g., 1Gi limit, using 1Gi)
7. Application performance degrades before crash (swap thrashing)
8. Container cannot allocate new memory despite heap space available
9. Pod memory usage grows over time (memory leak)
10. Multiple pods on same node OOMKilled simultaneously

## Impact
- **Availability**: Pod repeatedly crashes, service unavailable
- **Data loss**: In-flight transactions lost, cache data evicted
- **Cascading failures**: OOMKilled pod may trigger failover, impacting other services
- **Batch jobs**: Long-running jobs terminate before completion
- **User experience**: Increased latency from pod restarts, session loss

## Possible Root Causes
1. **Memory leak**: Application holds references preventing garbage collection
2. **Insufficient limit**: Container limit too low for actual workload
3. **Load spike**: Unexpected traffic increase causes memory usage spike
4. **Large object allocation**: Processing large file/dataset not expected
5. **Caching without eviction**: Cache grows unbounded without eviction policy
6. **Connection pool leak**: Connections not properly closed, consuming resources
7. **Thread leak**: Threads created but not cleaned up
8. **Inefficient query**: Database query returns massive result set
9. **Memory fragmentation**: Available memory fragmented, unable to allocate contiguous blocks
10. **Third-party library bug**: Dependency library contains memory leak

## Investigation Steps

### Step 1: Confirm OOMKilled Status
```bash
# Get pod status and last termination reason
kubectl describe pod <pod-name> -n <namespace> | grep -A 5 "Last State"

# Exit code 137 = signal 9 (SIGKILL)
# Exit code 1 = application error
# Verify termination reason is OOMKilled
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.containerStatuses[0].lastState.terminated}'

# Check if this is repeated pattern
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.containerStatuses[0].restartCount}'
```

### Step 2: Check Memory Limits and Requests
```bash
# Get memory limits and requests
kubectl describe pod <pod-name> -n <namespace> | grep -A 5 "Limits\|Requests"

# Verify limits make sense for workload
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.containers[0].resources}'

# Check deployment limits vs actual usage
kubectl get deployment <deployment-name> -n <namespace> -o jsonpath='{.spec.template.spec.containers[0].resources}'

# Compare with similar workloads
kubectl get pods -n <namespace> -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].resources.limits.memory}{"\n"}{end}'
```

### Step 3: Analyze Memory Usage Patterns
```bash
# Get current memory usage (requires metrics-server)
kubectl top pod <pod-name> -n <namespace>

# Get memory usage over time using Prometheus
# Query: rate(container_memory_rss_bytes[5m])

# Stream memory usage in real-time
kubectl exec <pod-name> -n <namespace> -- top -b -n 1 | head -20

# Get memory usage from inside container
kubectl exec <pod-name> -n <namespace> -- cat /proc/meminfo

# Check RSS (resident set size) vs VSZ (virtual memory)
kubectl exec <pod-name> -n <namespace> -- ps aux | grep <process-name>
```

### Step 4: Check Node Memory Pressure
```bash
# Check node conditions and memory pressure
kubectl describe node <node-name> | grep -A 10 "Conditions:"

# Check node available memory
kubectl top node <node-name>

# Check memory allocatable vs requested
kubectl describe node <node-name> | grep -A 15 "Allocated resources"

# Check for memory pressure on node
kubectl get nodes -o json | jq '.items[] | {name: .metadata.name, pressure: .status.conditions[] | select(.type=="MemoryPressure")}'
```

### Step 5: Examine Application Logs for Memory Issues
```bash
# Get logs before OOM (previous container instance)
kubectl logs <pod-name> -n <namespace> --previous | tail -100

# Check for memory-related errors
kubectl logs <pod-name> -n <namespace> --previous | grep -i "memory\|oom\|heap\|malloc"

# Get current logs if restarted
kubectl logs <pod-name> -n <namespace> | head -50

# Check for garbage collection logs (Java)
kubectl logs <pod-name> -n <namespace> --previous | grep -i "gc\|garbage collection"
```

### Step 6: Check Kubelet OOM Events
```bash
# SSH to affected node
ssh <node-ip>

# Check kernel OOM killer messages
dmesg | grep -i "Out of memory" | tail -20

# Check system memory usage
free -h

# Check memory usage by cgroup
cat /sys/fs/cgroup/memory/memory.usage_in_bytes
cat /sys/fs/cgroup/memory/memory.limit_in_bytes

# Get detailed OOM event
journalctl -u kubelet -n 50 | grep -i "oom"
```

### Step 7: Analyze Memory Consumption Details
```bash
# Get memory map of process (if application supports)
kubectl exec <pod-name> -n <namespace> -- cat /proc/<pid>/maps

# Check memory statistics
kubectl exec <pod-name> -n <namespace> -- cat /proc/<pid>/status | grep -E "VmRSS|VmSize|VmPeak"

# Monitor memory in real-time
kubectl exec <pod-name> -n <namespace> -- watch -n 1 'cat /proc/meminfo | head -10'

# Check open file descriptors (can consume memory)
kubectl exec <pod-name> -n <namespace> -- ls -1 /proc/<pid>/fd | wc -l
```

### Step 8: Check for Resource Leaks
```bash
# For Java applications, check heap usage
kubectl exec <pod-name> -n <namespace> -- jmap -heap <pid>

# For Java, get full heap dump before crash
kubectl exec <pod-name> -n <namespace> -- jmap -dump:live,format=b,file=heap.bin <pid>

# For Python applications, check object counts
kubectl exec <pod-name> -n <namespace> -- python -c "import sys; sys.gettrace()"

# Check database connections
kubectl exec <pod-name> -n <namespace> -- netstat -an | grep ESTABLISHED | wc -l
```

### Step 9: Verify cgroup Limits Are Applied
```bash
# Check cgroup memory settings
kubectl exec <pod-name> -n <namespace> -- cat /sys/fs/cgroup/memory/memory.limit_in_bytes

# Verify memory accounting
kubectl exec <pod-name> -n <namespace> -- cat /sys/fs/cgroup/memory/memory.stat

# Check if limit is being enforced
docker inspect <container-id> | grep -A 10 '"Memory"'
```

### Step 10: Look for Recent Code Changes
```bash
# Check deployment rollout history
kubectl rollout history deployment/<deployment-name> -n <namespace>

# Compare previous working version to current
kubectl rollout history deployment/<deployment-name> -n <namespace> --revision=<revision>

# Check if deployment recently changed
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | grep <deployment-name>

# Review git history for memory-related changes
git log --oneline -20 -- <path-to-application>
```

## Resolution Steps

### Immediate: Increase Memory Limit (Temporary)
```bash
# Increase memory limit to reduce immediate crashes
kubectl set resources deployment/<deployment-name> \
  -n <namespace> \
  --limits=memory=2Gi

# Watch for pod restart
kubectl rollout status deployment/<deployment-name> -n <namespace>

# If pod still crashes, increase further
kubectl set resources deployment/<deployment-name> \
  -n <namespace> \
  --limits=memory=4Gi
```

### For Memory Leaks: Add Monitoring
```bash
# Deploy memory profiler sidecar
kubectl patch deployment <deployment-name> -n <namespace> -p \
  '{"spec":{"template":{"spec":{"containers":[{"name":"memory-profiler","image":"memory-profiler:latest"}]}}}}'

# Or enable built-in profiling in application
# (Example for Python: add memory_profiler decorator to functions)

# Collect heap dumps periodically
kubectl exec <pod-name> -n <namespace> -- sh -c \
  'while true; do jmap -dump:live,format=b,file=heap-$(date +%s).bin <pid>; sleep 300; done &'
```

### For Load Spike: Auto-Scaling
```bash
# Configure Horizontal Pod Autoscaler
kubectl autoscale deployment <deployment-name> \
  --min=2 --max=10 \
  --cpu-percent=80 \
  -n <namespace>

# Or update existing HPA
kubectl set env deployment/<deployment-name> \
  -n <namespace> \
  MAX_MEMORY=2Gi
```

### For Inefficient Queries: Optimize Code
```bash
# Add pagination to large queries
# Replace: SELECT * FROM large_table
# With: SELECT * FROM large_table LIMIT 1000 OFFSET 0

# Implement result streaming instead of loading all into memory
# Add query indexes to reduce result sets
# Use database connection pool with size limit

# Restart application after code fix
kubectl rollout restart deployment/<deployment-name> -n <namespace>
```

## Validation
```bash
# Pod should stay in Running state without crashing
kubectl get pod <pod-name> -n <namespace> --watch

# Restart count should stabilize
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.containerStatuses[0].restartCount}'

# Memory usage should stabilize below limit
kubectl top pod <pod-name> -n <namespace> --containers

# Node memory should show available capacity
kubectl top node <node-name>

# No new OOM events should appear
dmesg | grep "Out of memory" | tail
```

## Prevention
- Set memory requests equal to or slightly below limits
- Implement memory limits based on actual profiling, not guesses
- Use memory profiling tools during development and testing
- Implement garbage collection tuning for Java/Python applications
- Add memory metrics monitoring and alerting
- Set up circuit breakers for result set sizes
- Implement connection pool size limits
- Review and test memory usage under peak load before production
- Regularly profile applications for memory leaks
- Use ephemeral storage for temporary data instead of memory

## Severity
**P1** - Causes service crashes and data loss, requires immediate action.

## Escalation Matrix
| Duration | Action |
|----------|--------|
| < 2 min | Increase memory limit as stopgap |
| 2-10 min | Analyze logs for memory leak patterns |
| 10-20 min | Engage application team for code review |
| 20-30 min | Plan permanent code fix or capacity upgrade |
| > 30 min | Declare P1 incident, page on-call leads |
