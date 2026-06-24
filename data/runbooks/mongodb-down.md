# MongoDB Down Runbook

## Problem
MongoDB service is unavailable or unreachable, preventing data read/write operations. Application cannot connect to database, causing service degradation or outage.

## Symptoms
1. MongoDB connection refused or timeout
2. Application logs show "connect ECONNREFUSED"
3. MongoDB pod not responding
4. Replica set unavailable
5. No primary elected
6. Connection to replica set members fails
7. Database queries timeout
8. Application cache fallback activated
9. Data writes queued/dropped
10. MongoDB pod restarting repeatedly

## Investigation Steps

### Step 1: Check MongoDB Pod Status
```bash
# Get MongoDB pod status
kubectl get pod <mongo-pod> -n <namespace>
kubectl describe pod <mongo-pod> -n <namespace>

# Check pod events
kubectl get events -n <namespace> --field-selector involvedObject.name=<mongo-pod>

# Check logs
kubectl logs <mongo-pod> -n <namespace> | tail -50

# Check restart count
kubectl get pod <mongo-pod> -n <namespace> -o jsonpath='{.status.containerStatuses[0].restartCount}'
```

### Step 2: Test MongoDB Connectivity
```bash
# Connect to MongoDB pod
kubectl exec -it <mongo-pod> -n <namespace> -- mongosh

# Or from app pod
kubectl exec -it <app-pod> -n <namespace> -- mongosh --host <mongo-host> --port 27017

# Test basic command
db.adminCommand({ping: 1})

# If successful, should return: { ok: 1 }
```

### Step 3: Check MongoDB Replica Set Status
```bash
# Connect to MongoDB
kubectl exec -it <mongo-pod> -n <namespace> -- mongosh

# Get replica set status
rs.status()

# Check members and their health
# Should see all members with state 1 (Primary) or 2 (Secondary)

# Get current primary
rs.isMaster()

# Get replica set configuration
rs.conf()
```

### Step 4: Check MongoDB Resource Usage
```bash
# Get pod resource metrics
kubectl top pod <mongo-pod> -n <namespace>

# Check resource limits
kubectl get pod <mongo-pod> -n <namespace> -o jsonpath='{.spec.containers[0].resources}'

# Check if OOMKilled
kubectl describe pod <mongo-pod> -n <namespace> | grep -i "oomkilled"

# Check node resources
kubectl top node <node>
```

### Step 5: Check MongoDB Data Integrity
```bash
# Connect to MongoDB
kubectl exec -it <mongo-pod> -n <namespace> -- mongosh

# Check database status
db.stats()

# Verify collections exist
db.getCollectionNames()

# Run database validation
db.validate()

# Check for corrupted oplog
rs.printReplicationInfo()

# Check if data directory accessible
df /data/db
```

### Step 6: Check MongoDB Storage
```bash
# Check data directory size
kubectl exec <mongo-pod> -n <namespace> -- du -sh /data/db

# Check if disk full
kubectl exec <mongo-pod> -n <namespace> -- df -h /data

# Check for corrupted WiredTiger files
kubectl exec <mongo-pod> -n <namespace> -- ls -lh /data/db/WiredTiger*

# Check if repair needed (corrupted files)
# Look for: "Unsupported version of WT..." in logs
```

### Step 7: Check MongoDB Logs for Errors
```bash
# Get MongoDB container logs
kubectl logs <mongo-pod> -n <namespace> | grep -i "error\|fail\|fatal" | tail -50

# Check for specific errors
kubectl logs <mongo-pod> -n <namespace> | grep -i "corrupt\|assertion\|terminating"

# Check for replication lag
kubectl logs <mongo-pod> -n <namespace> | grep -i "lag\|stale" | tail -20

# Check for connection errors
kubectl logs <mongo-pod> -n <namespace> | grep -i "accept.*fail\|connection.*reset"
```

### Step 8: Check Network Connectivity
```bash
# Test network from app pod
kubectl run -it --rm curl --image=nicolaka/netshoot --restart=Never -- \
  telnet <mongo-host> 27017

# Test DNS resolution
kubectl exec <app-pod> -n <namespace> -- nslookup <mongo-service>

# Check service endpoints
kubectl get endpoints <mongo-service> -n <namespace>

# If no endpoints, MongoDB pods not ready
```

### Step 9: Check Replica Set Elections
```bash
# Connect to MongoDB
kubectl exec -it <mongo-pod> -n <namespace> -- mongosh

# Check if there's a primary
rs.isMaster() | grep primary

# If no primary, check election logs
# Look for: "not running for primary"

# Manually trigger election (if stuck)
rs.stepDown()

# Wait for new primary election
sleep(5)
rs.isMaster()
```

### Step 10: Check MongoDB Service
```bash
# Verify MongoDB service exists
kubectl get svc <mongo-service> -n <namespace>

# Check service selector matches pods
kubectl get svc <mongo-service> -n <namespace> -o yaml | grep -A 5 "selector:"

# Verify pod labels match selector
kubectl get pod <mongo-pod> -n <namespace> -o yaml | grep -A 3 "labels:"

# Check if service has endpoints
kubectl get endpoints <mongo-service> -n <namespace>
```

## Resolution Steps

### If MongoDB Pod Crashed: Restart
```bash
# Delete pod (StatefulSet will recreate)
kubectl delete pod <mongo-pod> -n <namespace>

# Monitor restart
kubectl get pod <mongo-pod> -n <namespace> --watch

# Check logs
kubectl logs <mongo-pod> -n <namespace>
```

### If Out of Memory: Increase Limits
```bash
# Increase memory limit
kubectl set resources statefulset/<mongo-statefulset> \
  -n <namespace> \
  --limits=memory=4Gi

# Redeploy
kubectl rollout restart statefulset/<mongo-statefulset> -n <namespace>

# Or reduce data/cache size
kubectl exec <mongo-pod> -n <namespace> -- mongosh -e \
  "db.adminCommand({setParameter: 1, wiredTigerEngineRuntimeConfig: 'cache_size=2G'})"
```

### If Data Corrupted: Repair Database
```bash
# Stop MongoDB
kubectl patch statefulset <mongo-statefulset> -n <namespace> -p \
  '{"spec":{"replicas":0}}'

# Repair (from node)
ssh <node>
mongod --dbpath /data/db --repair

# Restart MongoDB
kubectl patch statefulset <mongo-statefulset> -n <namespace> -p \
  '{"spec":{"replicas":3}}'
```

### If Replica Set Broken: Reinitialize
```bash
# Connect to MongoDB
kubectl exec -it <mongo-pod> -n <namespace> -- mongosh

# Check replica set status
rs.status()

# If cannot reach majority, force reconfiguration
# WARNING: Can cause data loss

cfg = rs.conf()
cfg.members = [{_id: 0, host: "<primary-pod>:27017"}]
rs.reconfig(cfg, {force: true})

# Wait for recovery
sleep(5)
rs.status()
```

### If No Primary Elected: Manually Initiate
```bash
# Connect to any MongoDB pod
kubectl exec -it <mongo-pod> -n <namespace> -- mongosh

# Check if replica set initialized
rs.status()

# If not, manually initialize
rs.initiate({
  _id: "rs0",
  members: [
    {_id: 0, host: "<pod-0>:27017"},
    {_id: 1, host: "<pod-1>:27017"},
    {_id: 2, host: "<pod-2>:27017"}
  ]
})

# Wait for election
sleep(10)
rs.isMaster()
```

## Validation
```bash
# MongoDB should be accessible
kubectl exec -it <mongo-pod> -n <namespace> -- mongosh -e "db.adminCommand({ping: 1})"

# Should return: { ok: 1 }

# Replica set should have primary
kubectl exec -it <mongo-pod> -n <namespace> -- mongosh -e "rs.status()" | grep "PRIMARY"

# Application should connect successfully
kubectl logs <app-pod> -n <namespace> | grep -i "connected\|connected"

# No connection errors
kubectl logs <app-pod> -n <namespace> | grep -i "refused\|timeout" | wc -l
```

## Prevention
- Use StatefulSets for MongoDB with persistent volumes
- Configure health checks (liveness/readiness probes)
- Monitor replica set member health continuously
- Set up automated backups
- Configure log rotation to prevent disk full
- Monitor connection pool utilization
- Use MongoDB Atlas for managed service (if possible)
- Set up alerts for replica set member failures
- Regular testing of failover scenarios

## Severity
**P1** - Database unavailable, all data operations fail.

## Escalation Matrix
| Time | Action |
|------|--------|
| < 5 min | Check pod status, restart |
| 5-15 min | Investigate replication status |
| 15-30 min | Repair database or reinitialize |
| > 30 min | Page database team |
