# PostgreSQL Replication Lag Runbook

## Problem
PostgreSQL replica falls behind primary, with WAL (Write-Ahead Log) log files accumulating. Data on replica becomes stale, potentially causing inconsistency if failover occurs.

## Symptoms
1. Replication lag increasing continuously
2. WAL archive directory filling up
3. Replica cannot keep up with primary throughput
4. `pg_stat_replication` shows high lsn_write_lag
5. Replica query results outdated
6. WAL log files not being cleaned up
7. Disk space on primary increasing rapidly
8. Replica CPU/network at high utilization
9. Streaming replication status shows "catching up"
10. Failover impossible (replica too far behind)

## Impact
- **Data consistency**: Queries on replica see old data
- **Failover risk**: Cannot switch to replica safely
- **Disk space**: Primary disk fills with WAL files
- **Recovery**: Longer RTO if primary fails

## Investigation Steps

### Step 1: Check Replication Status
```bash
# Connect to primary
kubectl exec -it <postgres-primary> -n <namespace> -- \
  psql -U postgres -c "SELECT * FROM pg_stat_replication;"

# Check current LSN on primary
kubectl exec <postgres-primary> -n <namespace> -- \
  psql -U postgres -c "SELECT pg_current_wal_lsn();"

# Check LSN on replica
kubectl exec <postgres-replica> -n <namespace> -- \
  psql -U postgres -c "SELECT pg_last_xact_replay_lsn();"

# Calculate lag bytes
# difference = primary_lsn - replica_lsn

# Check replication connection
kubectl exec <postgres-primary> -n <namespace> -- \
  psql -U postgres -c "SELECT pid, usename, application_name, client_addr, state FROM pg_stat_activity WHERE state LIKE '%replication%';"
```

### Step 2: Check Replica Lag Over Time
```bash
# Monitor replication lag
kubectl exec <postgres-primary> -n <namespace> -- \
  psql -U postgres -c \
  "SELECT slot_name, restart_lsn, confirmed_flush_lsn FROM pg_replication_slots;"

# Get lag in bytes
kubectl exec <postgres-primary> -n <namespace> -- \
  psql -U postgres -c \
  "SELECT slot_name, pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn) as lag_bytes FROM pg_replication_slots;"

# Convert bytes to approximate time lag
# lag_time ≈ lag_bytes / (throughput_bytes_per_second)
```

### Step 3: Check Replica Resource Usage
```bash
# Monitor replica resource usage
kubectl top pod <postgres-replica> -n <namespace>

# Check CPU
top -b -n 1 | grep postgres

# Check network I/O
# Monitor bytes from primary over time

# Check disk I/O
iostat -x 1 5

# If CPU or network bottleneck, replica cannot catch up
```

### Step 4: Check WAL Archiving
```bash
# Check WAL file count
ls -1 /var/lib/postgresql/pg_wal/*.gz | wc -l

# Check for segment accumulation
ls -lh /var/lib/postgresql/pg_wal/ | head -20

# Check archiving status
kubectl exec <postgres-primary> -n <namespace> -- \
  psql -U postgres -c "SELECT * FROM pg_stat_archiver;"

# If archiving failed, WAL files accumulate on primary
```

### Step 5: Check Replica Apply Speed
```bash
# Monitor replay progress
kubectl exec <postgres-replica> -n <namespace> -- \
  psql -U postgres -c "SELECT now(), pg_last_xact_replay_lsn();" | tee start.log

# Wait 10 seconds
sleep 10

# Check again
kubectl exec <postgres-replica> -n <namespace> -- \
  psql -U postgres -c "SELECT now(), pg_last_xact_replay_lsn();" | tee end.log

# Calculate: (end_lsn - start_lsn) / 10 seconds = bytes_per_second
# If < 100KB/s = slow, check for bottlenecks
```

### Step 6: Check Replication Slot Status
```bash
# Check replication slots on primary
kubectl exec <postgres-primary> -n <namespace> -- \
  psql -U postgres -c "SELECT * FROM pg_replication_slots;"

# Check if slot active
kubectl exec <postgres-primary> -n <namespace> -- \
  psql -U postgres -c "SELECT slot_name, active, restart_lsn FROM pg_replication_slots WHERE slot_type='physical';"

# If slot inactive, replica disconnected
# Cannot resume replication without resync

# Get oldest LSN needed
kubectl exec <postgres-primary> -n <namespace> -- \
  psql -U postgres -c "SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) as oldest_bytes FROM pg_replication_slots;"
```

### Step 7: Check Network Connectivity
```bash
# Test network from replica to primary
kubectl exec <postgres-replica> -n <namespace> -- \
  telnet <postgres-primary-host> 5432

# Check replication connection status
kubectl exec <postgres-primary> -n <namespace> -- \
  psql -U postgres -c "SELECT * FROM pg_stat_activity WHERE backend_type='walsender';"

# If no walsender, replica not connected
```

### Step 8: Check Replica Configuration
```bash
# Check replica hot_standby setting
kubectl exec <postgres-replica> -n <namespace> -- \
  psql -U postgres -c "SHOW hot_standby;"

# Should be 'on' to allow queries

# Check max_wal_senders (primary)
kubectl exec <postgres-primary> -n <namespace> -- \
  psql -U postgres -c "SHOW max_wal_senders;"

# Should be >= number of replicas

# Check wal_level (primary)
kubectl exec <postgres-primary> -n <namespace> -- \
  psql -U postgres -c "SHOW wal_level;"

# Should be 'replica' or higher
```

### Step 9: Check Primary Disk Usage
```bash
# SSH to primary
ssh <postgres-primary-ip>

# Check WAL directory size
du -sh /var/lib/postgresql/pg_wal/

# List WAL files
ls -lh /var/lib/postgresql/pg_wal/*.gz | tail -20

# Check if filling up
df -h /var/lib/postgresql/

# If > 80%, urgent action needed
```

### Step 10: Check Replication Conflicts
```bash
# Check for replication conflicts
kubectl exec <postgres-replica> -n <namespace> -- \
  psql -U postgres -c "SELECT * FROM pg_stat_database_conflicts;"

# If conflicts > 0, queries on replica are canceling

# Check conflicting queries
kubectl exec <postgres-replica> -n <namespace> -- \
  psql -U postgres -c "SELECT * FROM pg_locks WHERE waitlocked;"

# Reduce conflict chance by reducing hot_standby_feedback_timeout
```

## Resolution Steps

### If Replica Too Far Behind: Resync
```bash
# Option 1: Base backup (full resync)
kubectl exec <postgres-replica> -n <namespace> -- \
  pg_basebackup -h <primary-host> -U replication -D /var/lib/postgresql/data -X stream -P

# Then restart replica
kubectl rollout restart statefulset/<postgres-replica-statefulset> -n <namespace>

# Option 2: WAL shipping (faster if small gap)
# Copy missing WAL files from primary to replica
# And resume replication
```

### If Replica Slow: Increase Resources
```bash
# Increase CPU
kubectl set resources statefulset/<postgres-replica> \
  -n <namespace> \
  --requests=cpu=2000m --limits=cpu=4000m

# Increase memory for larger cache
kubectl set resources statefulset/<postgres-replica> \
  -n <namespace> \
  --requests=memory=4Gi --limits=memory=8Gi

# Redeploy
kubectl rollout restart statefulset/<postgres-replica> -n <namespace>
```

### If WAL Files Accumulating: Increase Wal_keep_size
```bash
# On primary, increase retention
kubectl exec <postgres-primary> -n <namespace> -- \
  psql -U postgres -c "ALTER SYSTEM SET wal_keep_size='10GB';"

# Reload config
kubectl exec <postgres-primary> -n <namespace> -- \
  psql -U postgres -c "SELECT pg_reload_conf();"

# This keeps more WAL files locally, reducing need to archive
```

### If Replica Disconnected: Reconnect
```bash
# Check replication slot on primary
kubectl exec <postgres-primary> -n <namespace> -- \
  psql -U postgres -c "SELECT * FROM pg_replication_slots WHERE slot_name='<replica_name>';"

# If slot exists but inactive, restart replica
kubectl rollout restart statefulset/<postgres-replica-statefulset> -n <namespace>

# If slot missing, recreate it
kubectl exec <postgres-primary> -n <namespace> -- \
  psql -U postgres -c "SELECT * FROM pg_create_physical_replication_slot('<replica_name>');"
```

## Validation
```bash
# Replication lag should decrease
kubectl exec <postgres-primary> -n <namespace> -- \
  psql -U postgres -c "SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn) FROM pg_replication_slots;"

# Should be < 1GB and decreasing

# Replica should be catching up
# Monitor replay_lsn growth over time

# Queries on replica should see recent data
```

## Prevention
- Monitor replication lag continuously
- Alert when lag > 1GB or growing
- Size replica resources same as primary
- Use replication slots to prevent WAL removal
- Implement base backup automation
- Test failover regularly
- Monitor WAL archiving success
- Set up patroni/other HA solutions

## Severity
**P2** - Replica falling behind, failover unsafe, requires investigation.

## Escalation Matrix
| Lag Size | Action |
|----------|--------|
| < 100MB | Monitor |
| 100MB-1GB | Investigate bottleneck |
| > 1GB | Resync or scale replica |
| Disconnected | Immediate reconnect |
