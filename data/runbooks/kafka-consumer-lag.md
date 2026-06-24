# Kafka Consumer Lag Runbook

## Problem
Kafka consumer group falls behind, with lag continuously increasing. Messages are produced faster than consumed, causing delayed message processing and potential data loss if retention is exceeded.

## Symptoms
1. Consumer lag metric increases continuously
2. Messages processed timestamp far behind current time
3. Kafka topic retention warning or auto-deletion
4. Downstream systems receive delayed data
5. Consumer rebalancing occurring repeatedly
6. Consumer sessions timeout and restart
7. Consumer group shows "Dead" or "Empty" status
8. Partition reassignment pending
9. Broker logs show high I/O or network utilization
10. Zero throughput being processed despite available messages

## Impact
- **Data freshness**: Real-time analytics delayed
- **Alerting**: Alerts based on data reach systems late
- **Inconsistency**: Downstream systems out of sync
- **Data loss**: Old messages deleted before processing

## Possible Root Causes
1. **Slow consumer**: Application processing too slowly
2. **Consumer crash**: Consumer pod restarting repeatedly
3. **Long processing time**: Heavy computation per message
4. **GC pauses**: Java GC causing processing stalls
5. **Network issues**: Broker unreachable, retries slow
6. **Resource constraints**: Consumer CPU/memory limited
7. **Database bottleneck**: Insert/update bottleneck
8. **Broker issues**: Broker failing, rebalancing
9. **Session timeout**: Consumer session expires before processing completes
10. **Skipped messages**: Consumer code silently skipping messages

## Investigation Steps

### Step 1: Check Consumer Lag Metrics
```bash
# Get consumer group lag from Kafka
kubectl exec <kafka-pod> -n <namespace> -- kafka-consumer-groups.sh \
  --bootstrap-server <broker>:9092 \
  --group <consumer-group> \
  --describe

# Example output:
# TOPIC    PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
# events   0          1000000         1500000         500000

# Monitor lag over time with Prometheus
# Query: kafka_consumer_lag

# Get lag per partition
kubectl exec <kafka-pod> -n <namespace> -- kafka-consumer-groups.sh \
  --bootstrap-server <broker>:9092 \
  --group <consumer-group> \
  --describe \
  --sort-by-lag
```

### Step 2: Check Consumer Performance
```bash
# Get consumer throughput metrics
kubectl top pod <consumer-pod> -n <namespace>

# Check processing rate from logs
kubectl logs <consumer-pod> -n <namespace> | grep -i "processed\|messages" | tail -20

# Calculate messages per second
# Divide: lag_reduction_per_interval / time_interval

# Check if consumer is stuck
kubectl logs <consumer-pod> -n <namespace> | tail -50 | grep -c "."
# If same messages repeated, consumer stuck
```

### Step 3: Check Consumer Logs for Errors
```bash
# Look for processing errors
kubectl logs <consumer-pod> -n <namespace> | grep -i "error\|exception" | tail -50

# Check for timeouts
kubectl logs <consumer-pod> -n <namespace> | grep -i "timeout\|fail" | tail -30

# Look for skipped messages
kubectl logs <consumer-pod> -n <namespace> | grep -i "skip\|drop" | tail -20

# Check for dead letter queue routing
kubectl logs <consumer-pod> -n <namespace> | grep -i "dlq\|dead.*letter" | tail -20
```

### Step 4: Check Consumer Configuration
```bash
# Get consumer session timeout
kubectl get configmap <consumer-config> -n <namespace> -o yaml | grep -i "session.timeout\|max.poll"

# Check batch size
kubectl get configmap <consumer-config> -n <namespace> -o yaml | grep -i "batch\|fetch"

# Check processing timeout in code
grep -r "max.poll.records\|session.timeout.ms" <app-config>

# Example: If max.poll.records=500 and each takes 1 sec = 500 sec lag before rebalance
```

### Step 5: Check Kafka Broker Status
```bash
# Get broker metrics
kubectl exec <kafka-pod> -n <namespace> -- kafka-broker-api-versions.sh \
  --bootstrap-server <broker>:9092

# Check broker disk usage
kubectl exec <kafka-pod> -n <namespace> -- df -h /var/lib/kafka

# Check broker log retention
kubectl exec <kafka-pod> -n <namespace> -- kafka-log-dir.sh \
  --bootstrap-server <broker>:9092 \
  --describe | grep -i "size\|retention"

# Get broker resource usage
kubectl top pod <kafka-pod> -n <namespace>
```

### Step 6: Verify Partition Assignment
```bash
# Check current assignments
kubectl exec <kafka-pod> -n <namespace> -- kafka-consumer-groups.sh \
  --bootstrap-server <broker>:9092 \
  --group <consumer-group> \
  --describe \
  --members

# Check for unassigned partitions
# If any partition shows no member, not being consumed

# Check rebalancing status
kubectl describe pod <consumer-pod> -n <namespace> | grep -i "rebalance"

# Check failed consumer pod restarts
kubectl get pod <consumer-pod> -n <namespace> -o jsonpath='{.status.containerStatuses[0].restartCount}'
```

### Step 7: Check Message Processing
```bash
# Trace single message through consumer
kubectl logs <consumer-pod> -n <namespace> --tail=10000 | grep -E "msg-id|partition|offset" | head -50

# Check processing time per message
kubectl logs <consumer-pod> -n <namespace> | grep -E "processing.*\d+ms" | tail -20

# Look for batch processing metrics
# Log should show: "Processed 500 messages in 5000ms = 100 msg/sec"
```

### Step 8: Check Database Insert Performance
```bash
# If inserting to database, check bottleneck
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e "SHOW PROCESSLIST;" | grep "INSERT"

# Check write latency
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT * FROM performance_schema.events_statements_summary_by_digest WHERE digest_text LIKE '%INSERT%' ORDER BY SUM_TIMER_WAIT DESC LIMIT 5\\G"

# Check if connection pool exhausted
kubectl logs <consumer-pod> -n <namespace> | grep -i "connection.*pool"
```

### Step 9: Check Resource Constraints
```bash
# Check CPU throttling
kubectl exec <consumer-pod> -n <namespace> -- cat /sys/fs/cgroup/cpu/cpu.stat

# Check memory
kubectl top pod <consumer-pod> -n <namespace>

# Check if limits too low for workload
kubectl get pod <consumer-pod> -n <namespace> -o jsonpath='{.spec.containers[0].resources}'

# Check node resources
kubectl top node <node-name>
```

### Step 10: Monitor Real-Time Progress
```bash
# Watch lag decrease in real-time
watch -n 5 'kubectl exec <kafka-pod> -n <namespace> -- kafka-consumer-groups.sh \
  --bootstrap-server <broker>:9092 \
  --group <consumer-group> \
  --describe'

# Calculate catch-up time
# time_to_catchup = lag / (messages_per_second - messages_per_second_produced)
```

## Resolution Steps

### If Consumer Restarting: Fix Crashing Code
```bash
# Check crash logs
kubectl logs <consumer-pod> -n <namespace> --previous

# Fix issue in consumer code
# Common issues: uncaught exception, OOM, timeout

# Rebuild and deploy
kubectl set image deployment/<consumer-deployment> \
  consumer=<registry>/<image>:fixed-tag \
  -n <namespace>

# Monitor restart count
kubectl get pod <consumer-pod> -n <namespace> --watch
```

### If Processing Too Slow: Increase Consumers
```bash
# Scale consumer group to multiple replicas
kubectl scale deployment/<consumer-deployment> --replicas=5 -n <namespace>

# Kafka will rebalance partitions across consumers
# Each consumer processes fewer partitions, catches up faster

# Monitor rebalancing complete
kubectl logs <consumer-pod> -n <namespace> | grep -i "rebalance complete"
```

### If Session Timeout: Increase Timeout or Speed Up Processing
```bash
# Option 1: Increase session timeout (allows longer processing)
kubectl set env deployment/<consumer-deployment> \
  KAFKA_SESSION_TIMEOUT_MS=45000 \
  -n <namespace>

# Option 2: Reduce batch size (process fewer messages per session)
kubectl set env deployment/<consumer-deployment> \
  KAFKA_MAX_POLL_RECORDS=100 \
  -n <namespace>

# Redeploy
kubectl rollout restart deployment/<consumer-deployment> -n <namespace>
```

### If Database Insert Slow: Add Write Batching
```python
# Before (slow):
for message in messages:
    database.insert(message)  # One insert per message

# After (fast):
batch = []
for message in messages:
    batch.append(message)
    if len(batch) >= 1000:
        database.insert_batch(batch)  # Batch insert
        batch = []
```

### If Resource Constrained: Increase Limits
```bash
# Increase memory
kubectl set resources deployment/<consumer-deployment> \
  -n <namespace> \
  --limits=memory=2Gi

# Increase CPU
kubectl set resources deployment/<consumer-deployment> \
  -n <namespace> \
  --requests=cpu=1000m

# Redeploy
kubectl rollout restart deployment/<consumer-deployment> -n <namespace>
```

## Validation
```bash
# Lag should decrease
kubectl exec <kafka-pod> -n <namespace> -- kafka-consumer-groups.sh \
  --bootstrap-server <broker>:9092 \
  --group <consumer-group> \
  --describe | grep LAG

# Processing rate > production rate
# Example: lag should decrease by 1000+ messages per minute

# Consumer should be stable (no crashes/restarts)
kubectl get pod <consumer-pod> -n <namespace>

# Logs should show steady progress
kubectl logs <consumer-pod> -n <namespace> | tail -20 | grep -i "processed"
```

## Prevention
- Right-size consumer batch size and session timeout
- Monitor lag continuously with alerts at >100K
- Load test consumer at expected peak throughput
- Use multiple consumer instances for parallelism
- Implement circuit breaker for downstream failures
- Use async/non-blocking I/O for database inserts
- Monitor consumer rebalancing frequency (should be rare)
- Add consumer lag SLO to runbooks
- Document expected throughput for each consumer

## Severity
**P2** - Delays data delivery, requires investigation and optimization.

## Escalation Matrix
| Lag | Action |
|-----|--------|
| < 1K | Normal operation |
| 1K-10K | Monitor, check for errors |
| 10K-100K | Page engineer, investigate cause |
| 100K-1M | Scale up consumer replicas |
| > 1M | Declare P1, assess data loss risk |
