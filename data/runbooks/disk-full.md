# Disk Full Runbook

## Problem
Node or pod disk space exhausted, preventing writes and causing application failures. New log files cannot be written, temporary files fail to create.

## Symptoms
1. Disk usage at 100% (df -h shows 100%)
2. "No space left on device" errors in logs
3. Pod cannot write to ephemeral storage
4. Log files stop being written
5. Application fails with I/O errors
6. Pod evicted from node
7. Database cannot write to disk
8. Temporary file creation fails
9. System becomes sluggish or unresponsive
10. Node shows "DiskPressure" condition

## Possible Root Causes
1. **Large log files**: Logs grow unbounded without rotation
2. **Temp files accumulation**: /tmp or /var/tmp not cleaned
3. **Cache growth**: Cache directory grows without eviction
4. **Database files**: DB data directory too large
5. **Container images**: Too many images cached on node
6. **Failed deployment**: Aborted download/extraction
7. **No log rotation**: Logs never truncated
8. **PVC full**: Mounted persistent volume exhausted
9. **Inode exhaustion**: Too many small files
10. **Backup files**: Old backups not deleted

## Investigation Steps

### Step 1: Check Node Disk Usage
```bash
# SSH to node
ssh <node-ip>

# Get overall disk usage
df -h

# Identify which filesystem is full
df -h | grep "100%"

# Get partition details
lsblk

# If boot partition full, it's system issue
# If /var full, logs are culprit
# If /home full, user data issue
```

### Step 2: Find Large Files/Directories
```bash
# SSH to node
ssh <node-ip>

# Find largest directories
du -sh /* | sort -rh | head -10

# Find largest files
find / -type f -size +1G 2>/dev/null | head -20

# Check specific suspect locations
du -sh /var/lib/docker
du -sh /var/lib/kubelet
du -sh /var/log
du -sh /tmp

# Find files not accessed in 30 days
find / -type f -atime +30 2>/dev/null | head -20
```

### Step 3: Check Container Logs
```bash
# SSH to node
ssh <node-ip>

# Check kubelet log size
ls -lh /var/log/pods/*/*/

# Find massive log files
find /var/log/pods -type f -size +100M 2>/dev/null

# Check container logs
ls -lh /var/lib/docker/containers/*/

# Get log sizes per container
docker ps -a --format "table {{.ID}}\t{{.Status}}" | while read id status; do
  du -sh /var/lib/docker/containers/$id/
done
```

### Step 4: Check Docker/Containerd Usage
```bash
# SSH to node
ssh <node-ip>

# Docker disk usage
docker system df

# Containerd disk usage
du -sh /var/lib/containerd

# List images and their sizes
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | sort -k3 -h

# Unused images/containers
docker image prune -a --force --filter "until=72h"
```

### Step 5: Check Persistent Volume
```bash
# Check PVC status
kubectl get pvc -A

# Get PVC usage
kubectl exec <pod> -n <namespace> -- df -h /mnt/<volume>

# Find large files in mounted PVC
kubectl exec <pod> -n <namespace> -- du -sh /mnt/<volume>/* | sort -rh

# Check if quota exceeded
kubectl exec <pod> -n <namespace> -- df -i /mnt/<volume>
```

### Step 6: Check Log Rotation Configuration
```bash
# SSH to node
ssh <node-ip>

# Check logrotate configuration
cat /etc/logrotate.conf
cat /etc/logrotate.d/*

# Check if kubelet logs are rotated
grep -i "kubelet" /etc/logrotate.d/*

# Check if rotation is running
journalctl -u logrotate -n 20

# Check for failed rotations
journalctl -u logrotate | grep -i "error\|fail"
```

### Step 7: Check Database Size
```bash
# If PostgreSQL
kubectl exec <postgres-pod> -n <namespace> -- psql -U postgres -c "SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database ORDER BY pg_database_size DESC;"

# If MySQL
kubectl exec <mysql-pod> -n <namespace> -- mysql -u root -e "SELECT table_schema, ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) FROM information_schema.tables GROUP BY table_schema ORDER BY SUM(data_length + index_length) DESC;"

# If MongoDB
kubectl exec <mongo-pod> -n <namespace> -- mongo --eval "db.stats()"
```

### Step 8: Check Inode Usage
```bash
# SSH to node
ssh <node-ip>

# Check inode usage
df -i

# If close to limit, many small files present
# Find directories with many files
find / -type f 2>/dev/null | wc -l

# Find directories with most files
find / -maxdepth 3 -type d -exec bash -c 'echo "$(find "$0" -type f | wc -l) $0"' {} \; 2>/dev/null | sort -rn | head -10
```

### Step 9: Check Temporary Directories
```bash
# SSH to node
ssh <node-ip>

# Check /tmp
ls -lh /tmp | head -20
du -sh /tmp/*

# Check ephemeral storage on pods
kubectl exec <pod> -n <namespace> -- du -sh /tmp

# Check /var/tmp
ls -lh /var/tmp
du -sh /var/tmp/*

# Check pod ephemeral storage
kubectl describe pod <pod> -n <namespace> | grep -i "ephemeral"
```

### Step 10: Monitor Free Space Trend
```bash
# SSH to node
ssh <node-ip>

# Get current free space
df -h | head -5

# Check available inode percentage
df -i | head -5

# Monitor historical trend
# Query Prometheus: node_filesystem_avail_bytes
```

## Resolution Steps

### Immediate: Delete Old/Unused Files
```bash
# SSH to node
ssh <node-ip>

# Clean docker images (caution: may affect running containers)
docker image prune -a --force --filter "until=168h"

# Clean unused containers
docker container prune --force

# Clean stopped containers
docker container rm $(docker ps -aq -f "status=exited")

# Clean dangling volumes
docker volume prune --force

# Free space now should increase
df -h
```

### Remove Old Logs
```bash
# SSH to node
ssh <node-ip>

# Find and compress old logs
find /var/log -name "*.log" -mtime +30 -exec gzip {} \;

# Or delete old logs (caution!)
find /var/log -name "*.log" -mtime +30 -delete

# Restart kubelet to flush current logs
sudo systemctl restart kubelet

# Check freed space
df -h
```

### Enable Log Rotation if Missing
```bash
# SSH to node
ssh <node-ip>

# Create logrotate config for kubelet logs
cat > /etc/logrotate.d/kubelet <<EOF
/var/log/pods/*/*.log {
    daily
    missingok
    rotate 5
    compress
    delaycompress
    notifempty
    maxage 30
}
EOF

# Force immediate rotation
logrotate -f /etc/logrotate.conf

# Check freed space
df -h
```

### Clean Containerd/Docker
```bash
# SSH to node
ssh <node-ip>

# For containerd
ctr images ls | tail -n +2 | awk '{print $1}' | while read img; do
  ctr images remove $img
done

# Prune containerd storage
containerd cleanup

# For docker
docker system prune -a --volumes --force

# Check freed space
df -h
```

### If Pod Evicted: Recreate After Cleanup
```bash
# Verify free space
df -h

# Check if pod was evicted
kubectl get pod <pod> -n <namespace> | grep Evicted

# Delete evicted pod
kubectl delete pod <pod> -n <namespace>

# Pod should be recreated (if managed by deployment)
kubectl get pod <pod> -n <namespace> --watch
```

### If PVC Full: Resize PVC
```bash
# Check current PVC size
kubectl get pvc <pvc> -n <namespace> -o yaml | grep storage:

# Resize (if storage class allows)
kubectl patch pvc <pvc> -n <namespace> -p \
  '{"spec":{"resources":{"requests":{"storage":"100Gi"}}}}'

# Wait for resize completion
kubectl describe pvc <pvc> -n <namespace>
```

## Validation
```bash
# Disk usage should drop
df -h

# Nodes should not have DiskPressure condition
kubectl describe node <node> | grep DiskPressure

# Pods should no longer evicted
kubectl get pods -A | grep Evicted

# Applications should write logs normally
kubectl logs <pod> -n <namespace> | tail -5
```

## Prevention
- Configure log rotation with daily/size-based policy
- Set log retention: rotate logs after 7-30 days
- Monitor disk usage trends with alerts at 80%
- Clean temporary files automatically
- Use ephemeral storage limits to prevent runaway containers
- Implement log aggregation to reduce local disk
- Regular cleanup of old images/containers
- Monitor inode usage separately
- Use node autoscaler for capacity planning

## Severity
**P1** - Pods evicted, applications cannot write, service degraded.

## Escalation Matrix
| Free Space | Action |
|------------|--------|
| > 20% | Normal |
| 10-20% | Monitor, plan cleanup |
| 5-10% | Immediate cleanup needed |
| < 5% | Emergency: Delete old files |
| 0% | Node unusable, possible eviction |
