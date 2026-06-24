# Database Connection Pool Exhaustion Runbook

## Problem
Application cannot establish new database connections due to connection pool exhaustion. All available connections are held and not released, causing new requests to timeout waiting for an available connection.

## Symptoms
1. Application logs show "Connection pool exhausted" or "No available connections"
2. Database connection timeout errors for all new queries
3. Response times increase dramatically (timeout length)
4. Some requests complete normally while others timeout randomly
5. Connection count on database equals pool max size exactly
6. Connections remain in idle state rather than being released
7. Application becomes unresponsive to new requests
8. Database shows many idle connections from application
9. Restarting application immediately frees all connections
10. Issue occurs periodically or after specific operations

## Impact
- **Complete service degradation**: Application cannot process requests
- **User impact**: All requests timeout and fail
- **Data access blocked**: Cannot query or modify database
- **Cascade failures**: Other services depending on this service also fail
- **Recovery difficulty**: May require manual intervention to clear connections

## Possible Root Causes
1. **Unclosed connections**: Code doesn't return connections to pool after use
2. **Long-running queries**: Queries take longer than expected, hold connections
3. **Deadlocks**: Queries deadlock, holding connections indefinitely
4. **Network issues**: Connection lost but pool thinks connection still active
5. **Pool misconfiguration**: Pool size too small for actual load
6. **Connection validation failure**: Idle connections become invalid, not reused
7. **Exception during query**: Exception causes connection not returned to pool
8. **Synchronous querying**: Blocking I/O during request handling
9. **Cascading failure**: Slow database causes application to hold connections longer
10. **Third-party code leak**: Library code doesn't properly close connections

## Investigation Steps

### Step 1: Confirm Connection Pool Status
```bash
# Check application logs for pool-related errors
kubectl logs <pod-name> -n <namespace> | grep -i "pool\|connection\|timeout" | tail -50

# Get active connection count on database
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e "SHOW PROCESSLIST;" | wc -l

# Check connection by application
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT db, count(*) FROM information_schema.processlist GROUP BY db;"

# Show idle connections
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT * FROM information_schema.processlist WHERE command='Sleep' ORDER BY time DESC LIMIT 20;"
```

### Step 2: Check Connection Pool Configuration
```bash
# Get application connection pool settings from config
kubectl get configmap <app-config> -n <namespace> -o yaml | grep -i "pool\|connection\|max"

# Check database max connections
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e "SHOW VARIABLES LIKE 'max_connections';"

# Check default pool size in application
grep -r "maxPoolSize\|pool_size\|max_connections" <app-config>

# Verify environment variables override defaults
kubectl env pod <pod-name> -n <namespace> | grep -i "pool\|connection"
```

### Step 3: Identify Long-Running Queries
```bash
# Show currently running queries
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT id, time, state, info FROM information_schema.processlist WHERE command != 'Sleep' ORDER BY time DESC LIMIT 20;"

# Check if any queries are stuck
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT id, time, info FROM information_schema.processlist WHERE time > 60 ORDER BY time DESC;"

# Check slow query log
kubectl exec <db-pod> -n <namespace> -- tail -50 /var/log/mysql/slow.log

# Identify queries taking time
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT digest_text, count_star, avg_timer_wait/1000000000000 as avg_sec FROM performance_schema.events_statements_summary_by_digest ORDER BY avg_timer_wait DESC LIMIT 10\\G"
```

### Step 4: Check Connection Parameters
```bash
# Monitor connections by application/host
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT user, host, count(*) FROM information_schema.processlist GROUP BY user, host;"

# Check if connections are in "waiting for lock" state
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT * FROM information_schema.processlist WHERE state LIKE '%lock%';"

# Check for deadlocks
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e "SHOW ENGINE INNODB STATUS\\G" | grep -A 20 "LATEST DETECTED DEADLOCK"

# Check if connections are in other blocked states
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT state, count(*) FROM information_schema.processlist GROUP BY state ORDER BY count(*) DESC;"
```

### Step 5: Verify Application Connection Handling
```bash
# Check if connection handling code is correct
grep -r "getConnection\|executeQuery\|returnConnection\|close()" <app-code> | head -30

# Look for missing try-finally or try-with-resources blocks
grep -A10 "getConnection" <app-code> | grep -v "finally\|try"

# Check for exception handling
grep -B5 -A10 "executeQuery" <app-code> | grep -i "catch\|finally\|close"

# Monitor JVM connection pool metrics (if Java)
kubectl exec <pod-name> -n <namespace> -- jcmd <pid> GC.class_histogram | grep -i "connection"
```

### Step 6: Test Database Connectivity
```bash
# Test if database is slow or unresponsive
time kubectl exec <db-pod> -n <namespace> -- mysql -u root -e "SELECT 1;"

# Check database resource usage
kubectl exec <db-pod> -n <namespace> -- mysqladmin -u root extended-status | grep -i "questions\|slow\|lock"

# Check if database has connection limits
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SHOW VARIABLES LIKE '%max_connections%';"

# Check current connections vs max
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SHOW STATUS LIKE 'Threads_connected';"
```

### Step 7: Monitor Application Metrics
```bash
# Check application thread pool and queue depth
kubectl exec <pod-name> -n <namespace> -- curl http://localhost:8080/actuator/metrics/tomcat.threads.busy

# Get connection pool metrics from HikariCP (Java)
kubectl exec <pod-name> -n <namespace> -- curl http://localhost:8080/actuator/metrics/hikaricp.connections | jq .

# Check request queue size
kubectl exec <pod-name> -n <namespace> -- curl http://localhost:8080/actuator/metrics/tomcat.global.request | jq .

# Monitor over time
kubectl top pod <pod-name> -n <namespace> --watch
```

### Step 8: Check Application Logs for Errors
```bash
# Look for uncaught exceptions
kubectl logs <pod-name> -n <namespace> | grep -i "exception\|error" | grep -v "expected\|handled" | tail -30

# Check if exceptions occur during query execution
kubectl logs <pod-name> -n <namespace> | grep -B2 -A2 "SQLException\|QueryException"

# Look for connection return errors
kubectl logs <pod-name> -n <namespace> | grep -i "return\|close.*fail" | tail -20
```

### Step 9: Check Network Issues
```bash
# SSH to application pod
kubectl exec -it <pod-name> -n <namespace> -- bash

# Test database connectivity
nc -zv <db-host> 3306

# Check network statistics
netstat -an | grep ESTABLISHED | wc -l
netstat -an | grep ESTABLISHED | grep ":3306"

# Monitor network errors
cat /proc/net/netstat | grep TcpExt

# Check for connection resets
journalctl -u kubelet -n 50 | grep -i "reset\|timeout"
```

### Step 10: Analyze Idle Connection Age
```bash
# Show idle connections with start time
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT id, user, time, info FROM information_schema.processlist WHERE command='Sleep' ORDER BY time DESC LIMIT 20;"

# If time is very old, connection likely stuck/forgotten
# Connection should be returned to pool after query completes

# Check idle connection timeout configuration
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SHOW VARIABLES LIKE 'interactive_timeout';"
```

## Resolution Steps

### If Connections Leak: Emergency Restart
```bash
# Immediate: Restart application pods
kubectl rollout restart deployment/<deployment-name> -n <namespace>

# Monitor connection recovery
kubectl exec <db-pod> -n <namespace> -- watch -n 5 'mysql -u root -e "SHOW PROCESSLIST;" | wc -l'
```

### If Connections Properly Managed: Increase Pool Size
```bash
# Increase pool size temporarily while investigating
kubectl set env deployment/<deployment-name> \
  -n <namespace> \
  DB_POOL_SIZE=50

# Or update config
kubectl patch configmap <app-config> -n <namespace> -p \
  '{"data":{"db.pool.size":"50"}}'

# Redeploy
kubectl rollout restart deployment/<deployment-name> -n <namespace>
```

### If Long-Running Queries: Add Query Timeout
```bash
# Kill long-running query
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e "KILL <query-id>;"

# Set global query timeout
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SET GLOBAL max_statement_time=30000;"  # 30 seconds

# Or per-user
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "ALTER USER 'app-user'@'%' REQUIRE max_statement_time=30000;"

# Verify query timeout in effect
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SHOW VARIABLES LIKE 'max_statement_time';"
```

### If Deadlocks Detected: Kill Blocking Query
```bash
# Identify blocking query
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SHOW ENGINE INNODB STATUS\\G" | grep -A 20 "LATEST DETECTED DEADLOCK" | grep "KILL"

# Kill blocking query
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e "KILL <blocking-id>;"

# Or kill all queries from source
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT CONCAT('KILL ', id, ';') FROM information_schema.processlist WHERE host='<app-host>' AND command!='Sleep';" | \
  mysql -u root
```

### Fix Code: Add Try-With-Resources (Java)
```java
// Before (leak):
Connection conn = dataSource.getConnection();
ResultSet rs = conn.createStatement().executeQuery("SELECT ...");
// ...may crash here, connection never closed

// After (fixed):
try (Connection conn = dataSource.getConnection();
     Statement stmt = conn.createStatement();
     ResultSet rs = stmt.executeQuery("SELECT ...")) {
    // ...connection auto-closed when block exits
}
```

### Fix Code: Ensure Connections Returned
```python
# Before (leak):
conn = get_connection_from_pool()
data = execute_query(conn, sql)
# Exception here = connection never returned

# After (fixed):
try:
    conn = get_connection_from_pool()
    data = execute_query(conn, sql)
finally:
    return_connection_to_pool(conn)  # Always executed
```

## Validation
```bash
# Connection count should drop after fix
kubectl exec <db-pod> -n <namespace> -- \
  watch -n 5 'mysql -u root -e "SHOW PROCESSLIST;" | wc -l'

# Application should respond to requests
curl http://app-service/health

# Long-running queries resolved
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT time, info FROM information_schema.processlist WHERE command != 'Sleep' LIMIT 5;"

# No pool-related errors in logs
kubectl logs <pod-name> -n <namespace> | grep -i "pool\|connection.*timeout"
```

## Prevention
- Use connection pooling libraries with proper defaults (HikariCP, DBPool)
- Always use try-with-resources or try-finally for connection cleanup
- Set pool size based on actual load testing
- Configure connection validation on checkout/return
- Implement circuit breakers to fail fast
- Add monitoring and alerting for pool utilization
- Regular code review focusing on resource management
- Load test to identify connection leaks early
- Implement connection pool metrics monitoring
- Document connection usage patterns in team guidelines

## Severity
**P1** - Causes complete service outage, requires immediate response.

## Escalation Matrix
| Duration | Action |
|----------|--------|
| < 2 min | Kill hanging queries, restart app |
| 2-10 min | Increase pool size, enable monitoring |
| 10-30 min | Identify code leak source |
| 30-60 min | Deploy code fix |
| > 60 min | Page database and application teams |
