# Redis Down Runbook

## Problem
The Redis cache service is unreachable or unresponsive, preventing the application from writing to or reading from cache. This cascades to database as cache misses result in increased database load.

## Symptoms
1. Redis connection timeout errors in application logs
2. Application cannot execute cache operations (SET, GET)
3. Database query traffic increases dramatically (cache bypass)
4. Redis service unreachable from application pods
5. Response times increase due to direct database access
6. No metrics available from Redis (connection fails)
7. Redis pod shows `NotReady` or `CrashLoopBackOff`
8. Port 6379 (Redis default) not responding to connections
9. Redis CLI commands timeout or fail
10. Application degrades gracefully but throughput reduced

## Impact
- **Performance**: Application slows due to database-only access (no cache)
- **Database load**: Increased queries on backend database
- **Scalability**: Reduced ability to handle load without cache
- **User experience**: Increased response times
- **Cost**: Higher database resource usage

## Possible Root Causes
1. **Redis service crashed**: Container or process terminated
2. **Memory pressure**: Redis runs out of available memory
3. **Network issue**: Connection from pod to Redis blocked
4. **Port misconfiguration**: Redis listening on wrong port or not listening
5. **Firewall/NetworkPolicy**: Ingress traffic blocked
6. **Authentication failure**: Wrong password or missing credentials
7. **Resource limits**: CPU or memory limits cause throttling
8. **Disk full**: RDB persistence failed, Redis stopped
9. **Connection limit**: Max connections reached
10. **Third-party interference**: Another process on port 6379

## Investigation Steps

### Step 1: Check Redis Service Status
```bash
# Get Redis pod status
kubectl get pod <redis-pod> -n <namespace>
kubectl describe pod <redis-pod> -n <namespace>

# Check pod events
kubectl get events -n <namespace> --field-selector involvedObject.name=<redis-pod>

# Check pod logs
kubectl logs <redis-pod> -n <namespace>
kubectl logs <redis-pod> -n <namespace> --previous

# Check if pod is running
kubectl get pod <redis-pod> -n <namespace> -o jsonpath='{.status.phase}'
```

### Step 2: Test Connection from Application Pod
```bash
# Try to connect to Redis from application pod
kubectl exec -it <app-pod> -n <namespace> -- telnet <redis-host> 6379

# Or use redis-cli if available
kubectl exec -it <app-pod> -n <namespace> -- redis-cli -h <redis-host> ping

# Check DNS resolution of Redis host
kubectl exec <app-pod> -n <namespace> -- nslookup <redis-host>

# Test connection with timeout
kubectl exec <app-pod> -n <namespace> -- timeout 5 nc -zv <redis-host> 6379
```

### Step 3: Verify Redis Is Listening
```bash
# Check if Redis service exists
kubectl get svc <redis-service> -n <namespace>

# Check service endpoints (should have target pods)
kubectl get endpoints <redis-service> -n <namespace>

# SSH to Redis pod and check if port is listening
kubectl exec <redis-pod> -n <namespace> -- netstat -tlnp | grep 6379

# Check if Redis process is running
kubectl exec <redis-pod> -n <namespace> -- ps aux | grep redis
```

### Step 4: Check Redis Resource Usage
```bash
# Get Redis pod resource usage
kubectl top pod <redis-pod> -n <namespace>

# Check memory limits vs usage
kubectl get pod <redis-pod> -n <namespace> -o jsonpath='{.spec.containers[0].resources}'

# Get Redis memory stats from inside container
kubectl exec <redis-pod> -n <namespace> -- redis-cli INFO memory

# Check available memory on node
kubectl top node <node-name>

# Check if pod was OOMKilled
kubectl describe pod <redis-pod> -n <namespace> | grep -i "oomkilled\|memory"
```

### Step 5: Verify Network Connectivity
```bash
# Check network policy allowing traffic
kubectl get networkpolicies -n <namespace>
kubectl describe networkpolicy <policy> -n <namespace>

# Test network path
kubectl run -it --rm debug --image=nicolaka/netshoot --restart=Never -- \
  telnet <redis-host> 6379

# Check service DNS
kubectl run -it --rm debug --image=nicolaka/netshoot --restart=Never -- \
  nslookup <redis-service>

# Check firewall from pod
kubectl exec <redis-pod> -n <namespace> -- iptables -L
```

### Step 6: Check Redis Configuration
```bash
# Get Redis configuration from pod
kubectl exec <redis-pod> -n <namespace> -- redis-cli CONFIG GET "*"

# Check specific critical settings
kubectl exec <redis-pod> -n <namespace> -- redis-cli CONFIG GET maxmemory
kubectl exec <redis-pod> -n <namespace> -- redis-cli CONFIG GET port

# Check if binding only to localhost (wrong!)
kubectl exec <redis-pod> -n <namespace> -- redis-cli CONFIG GET bind

# Check if protected mode is enabled
kubectl exec <redis-pod> -n <namespace> -- redis-cli CONFIG GET protected-mode
```

### Step 7: Verify Persistence State
```bash
# Check RDB file status
kubectl exec <redis-pod> -n <namespace> -- ls -lh /data/dump.rdb

# Check for corrupted RDB file (Redis won't start)
kubectl exec <redis-pod> -n <namespace> -- redis-cli LASTSAVE

# Check save config
kubectl exec <redis-pod> -n <namespace> -- redis-cli CONFIG GET save

# Check disk space where RDB is saved
kubectl exec <redis-pod> -n <namespace> -- df -h /data/
```

### Step 8: Check Authentication
```bash
# Try redis-cli with and without password
kubectl exec <redis-pod> -n <namespace> -- redis-cli ping  # No auth
kubectl exec <redis-pod> -n <namespace> -- redis-cli -a <password> ping  # With auth

# Check if auth is required
kubectl exec <redis-pod> -n <namespace> -- redis-cli CONFIG GET requirepass

# Check application secrets for password
kubectl get secret <redis-secret> -n <namespace> -o jsonpath='{.data.password}' | base64 -d
```

### Step 9: Check Max Connections
```bash
# Get connected clients
kubectl exec <redis-pod> -n <namespace> -- redis-cli INFO clients

# Check max connections configuration
kubectl exec <redis-pod> -n <namespace> -- redis-cli CONFIG GET maxclients

# Count current connections
kubectl exec <redis-pod> -n <namespace> -- redis-cli CLIENT LIST | wc -l

# If maxed out, list connections
kubectl exec <redis-pod> -n <namespace> -- redis-cli CLIENT LIST | head -20
```

### Step 10: Check Application Error Logs
```bash
# Get application logs showing Redis errors
kubectl logs <app-pod> -n <namespace> | grep -i "redis\|connection.*refused\|timeout" | tail -50

# Look for retry patterns
kubectl logs <app-pod> -n <namespace> | grep -i "retry\|reconnect" | tail -20

# Check if application has circuit breaker activated
kubectl logs <app-pod> -n <namespace> | grep -i "circuit\|fallback" | tail -20
```

## Resolution Steps

### If Redis Pod Not Running: Restart
```bash
# Delete and recreate Redis pod
kubectl delete pod <redis-pod> -n <namespace>

# Or restart through deployment
kubectl rollout restart statefulset/<redis-statefulset> -n <namespace>

# Or restart through deployment
kubectl rollout restart deployment/<redis-deployment> -n <namespace>

# Monitor restart
kubectl get pod <redis-pod> -n <namespace> --watch
```

### If Out of Memory: Clear Cache or Increase Limit
```bash
# Flush all data (CAUTION: destroys all cache!)
kubectl exec <redis-pod> -n <namespace> -- redis-cli FLUSHALL

# Or set eviction policy to clear LRU data
kubectl exec <redis-pod> -n <namespace> -- redis-cli CONFIG SET maxmemory-policy allkeys-lru

# Increase memory limit in pod spec
kubectl set resources statefulset/<redis-statefulset> \
  -n <namespace> \
  --limits=memory=2Gi

# Restart pod to pick up new limit
kubectl rollout restart statefulset/<redis-statefulset> -n <namespace>
```

### If Port Misconfigured: Fix Configuration
```bash
# Update Redis config to listen on correct port
kubectl exec <redis-pod> -n <namespace> -- redis-cli CONFIG SET port 6379

# Or update through ConfigMap
kubectl patch configmap <redis-config> -n <namespace> -p \
  '{"data":{"redis.conf":"port 6379\nbind 0.0.0.0"}}'

# Restart Redis to apply config
kubectl rollout restart statefulset/<redis-statefulset> -n <namespace>
```

### If RDB File Corrupted: Remove and Recreate
```bash
# Stop Redis
kubectl rollout restart statefulset/<redis-statefulset> -n <namespace>

# Remove corrupted RDB file
kubectl exec <redis-pod> -n <namespace> -- rm -f /data/dump.rdb

# Start Redis (will start fresh without data)
kubectl rollout restart statefulset/<redis-statefulset> -n <namespace>

# Optionally restore from backup
# kubectl cp backup/dump.rdb <redis-pod>:/data/dump.rdb
```

### If NetworkPolicy Blocking: Update or Bypass
```bash
# Check network policy
kubectl get networkpolicies -n <namespace>

# Create exception for Redis traffic
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-redis
spec:
  podSelector:
    matchLabels:
      app: redis
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: application
    ports:
    - protocol: TCP
      port: 6379
EOF
```

### If High Latency: Check Slow Commands
```bash
# Get slow command log
kubectl exec <redis-pod> -n <namespace> -- redis-cli SLOWLOG GET 10

# Check specific command latency
kubectl exec <redis-pod> -n <namespace> -- redis-cli SLOWLOG GET | grep -i "<command>"

# Lower slow log threshold to catch more
kubectl exec <redis-pod> -n <namespace> -- redis-cli CONFIG SET slowlog-log-slower-than 1000

# Monitor in real-time
kubectl exec <redis-pod> -n <namespace> -- redis-cli MONITOR | head -50
```

## Validation
```bash
# Redis should be responding to PING
kubectl exec <redis-pod> -n <namespace> -- redis-cli ping

# Should return PONG
# Output: PONG

# Connection from application should work
kubectl exec <app-pod> -n <namespace> -- redis-cli -h <redis-host> ping

# Check connected clients
kubectl exec <redis-pod> -n <namespace> -- redis-cli INFO clients | grep connected_clients

# Application should cache data again
kubectl logs <app-pod> -n <namespace> | grep -i "cache.*hit" | head -5
```

## Prevention
- Use StatefulSet for Redis with persistent storage
- Set memory limits and eviction policy appropriately
- Implement health checks with readiness/liveness probes
- Monitor Redis memory and connection metrics
- Configure slow log monitoring
- Implement circuit breaker in application
- Regular backup of Redis data
- Test failover scenarios regularly
- Use Redis Sentinel for high availability
- Monitor RDB save operations and persistence

## Severity
**P2** - Degrades application performance, cascades to database, requires prompt resolution.

## Escalation Matrix
| Duration | Action |
|----------|--------|
| < 5 min | Check pod status, check logs |
| 5-15 min | Restart Redis pod |
| 15-30 min | Investigate root cause |
| 30-60 min | Apply fix or workaround |
| > 60 min | Escalate to infrastructure team |
