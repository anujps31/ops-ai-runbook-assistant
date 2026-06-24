# Database Deadlock Runbook

## Problem
Two or more database transactions are waiting for locks held by each other, causing queries to timeout and transactions to fail. Transactions cannot proceed, blocking application operations.

## Symptoms
1. Database returns "Deadlock detected" error
2. Queries timeout waiting for lock acquisition
3. Application sees "Deadlock found when trying to get lock"
4. Specific transaction frequently deadlocks
5. Concurrent operations on related tables fail
6. Database error rate spike
7. Transaction rollback failures
8. Long-running transaction creates wait queue
9. Application retry attempts exhaust
10. Multiple errors in application error logs

## Impact
- **Transaction failures**: Sensitive operations (payments, orders) fail
- **Data consistency**: Incomplete transactions leave inconsistent state
- **Availability**: Application cannot complete critical operations
- **User impact**: "Something went wrong" errors

## Investigation Steps

### Step 1: Get Deadlock Information
```bash
# Show latest deadlock
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e "SHOW ENGINE INNODB STATUS\\G" | \
  grep -A 30 "LATEST DETECTED DEADLOCK"

# Check deadlock logs
kubectl logs <db-pod> -n <namespace> | grep -i "deadlock" | tail -20

# Find which transactions are blocking
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT * FROM INFORMATION_SCHEMA.INNODB_LOCKS;"

# See wait-for relationships
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT * FROM INFORMATION_SCHEMA.INNODB_LOCK_WAITS;"
```

### Step 2: Identify Deadlock Participants
```bash
# Get current transactions
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT trx_id, trx_state, trx_started, trx_mysql_thread_id FROM INFORMATION_SCHEMA.INNODB_TRX ORDER BY trx_started\\G"

# See what locks each transaction holds
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT lock_id, lock_trx_id, lock_mode, lock_type, lock_table, lock_index FROM INFORMATION_SCHEMA.INNODB_LOCKS;"

# Get blocking relationships
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT * FROM INFORMATION_SCHEMA.INNODB_LOCK_WAITS\\G"
```

### Step 3: Analyze Table Access Patterns
```bash
# Check which tables involved in deadlock
# From LATEST DETECTED DEADLOCK output, look for TABLE and INDEX names

# Get table statistics
kubectl exec <db-pod> -n <namespace> -- mysql -u root <db> -e \
  "SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='<table>'\\G"

# Check indexes on affected tables
kubectl exec <db-pod> -n <namespace> -- mysql -u root <db> -e \
  "SHOW INDEX FROM <table>;"

# Get row-level lock information
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT * FROM INFORMATION_SCHEMA.INNODB_LOCKS WHERE LOCK_TABLE='<table>'\\G"
```

### Step 4: Review Transaction Isolation Level
```bash
# Check current isolation level
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT @@transaction_isolation;"

# Check per-session isolation level
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SHOW VARIABLES LIKE 'transaction_isolation';"

# Deadlock likely with READ_COMMITTED or REPEATABLE_READ
# Serializable prevents deadlock but slower

# Check innodb_lock_wait_timeout (default 50 sec)
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SHOW VARIABLES LIKE 'innodb_lock_wait_timeout';"
```

### Step 5: Check Query Execution Order
```bash
# Simulate transaction scenario
# If Transaction A: LOCK table1 then table2
# And Transaction B: LOCK table2 then table1
# = deadlock

# Get query history
kubectl exec <db-pod> -n <namespace> -- tail -1000 /var/log/mysql/slow.log | \
  grep -E "UPDATE|DELETE|INSERT" | head -20

# Check application code for transaction order
grep -r "BEGIN\|START TRANSACTION" <app-code>

# Look for inconsistent locking order across endpoints
```

### Step 6: Check Database Configuration
```bash
# Get innodb settings
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SHOW VARIABLES LIKE 'innodb%';" | grep -E "lock|timeout|autoinc"

# Check if innodb_deadlock_detect enabled
# (Default ON, but can be OFF in some configs)
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SHOW VARIABLES LIKE 'innodb_deadlock_detect';"

# Check lock wait timeout
# If too high (>50s), applications wait too long
```

### Step 7: Monitor Active Locks
```bash
# Real-time lock monitoring
watch -n 1 'kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT * FROM INFORMATION_SCHEMA.INNODB_LOCKS\\G" | wc -l'

# Get locks per table
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT lock_table, count(*) FROM INFORMATION_SCHEMA.INNODB_LOCKS GROUP BY lock_table;"

# Check for stale locks (transaction stuck)
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT trx_id, trx_started, timestampdiff(SECOND, trx_started, NOW()) as seconds FROM INFORMATION_SCHEMA.INNODB_TRX WHERE timestampdiff(SECOND, trx_started, NOW()) > 60;"
```

### Step 8: Analyze Application Code
```bash
# Look for explicit lock ordering in code
grep -r "SELECT.*FOR UPDATE" <app-code>

# Check for transactions spanning multiple tables
grep -B 5 -A 5 "BEGIN" <app-code>

# Look for non-transactional queries mixed with transactional
# This can cause lock waits

# Example deadlock pattern:
# Thread 1: UPDATE table1 WHERE id=1 -> UPDATE table2 WHERE id=1
# Thread 2: UPDATE table2 WHERE id=1 -> UPDATE table1 WHERE id=1
```

### Step 9: Check for Locks Held Too Long
```bash
# Find long-running transactions
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT trx_id, trx_mysql_thread_id, trx_started, NOW(), \
   timestampdiff(SECOND, trx_started, NOW()) as duration \
   FROM INFORMATION_SCHEMA.INNODB_TRX \
   WHERE timestampdiff(SECOND, trx_started, NOW()) > 30;"

# Get locks held by each transaction
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT trx_id, lock_mode, lock_type FROM INFORMATION_SCHEMA.INNODB_LOCKS \
   JOIN INFORMATION_SCHEMA.INNODB_TRX USING (trx_id);"

# Identify if queries waiting on specific locks
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT * FROM INFORMATION_SCHEMA.INNODB_LOCK_WAITS\\G"
```

### Step 10: Test Deadlock Scenario
```bash
# Create two sessions to reproduce
# Session 1:
BEGIN;
UPDATE <table> SET <column> = <value> WHERE id = 1;
UPDATE <other_table> SET <column> = <value> WHERE id = 2;
COMMIT;

# Session 2 (simultaneously):
BEGIN;
UPDATE <other_table> SET <column> = <value> WHERE id = 2;
UPDATE <table> SET <column> = <value> WHERE id = 1;
COMMIT;

# One session should get deadlock error
# Verify deadlock appears in LATEST DETECTED DEADLOCK
```

## Resolution Steps

### Immediate: Kill Blocking Transaction
```bash
# Get thread ID of blocking transaction
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SELECT trx_mysql_thread_id FROM INFORMATION_SCHEMA.INNODB_TRX ORDER BY trx_started LIMIT 1;"

# Kill the transaction
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "KILL <thread_id>;"

# Other waiting transactions should proceed
# Verify: SELECT * FROM INFORMATION_SCHEMA.INNODB_LOCKS (should be empty soon)
```

### Fix: Change Lock Ordering
```python
# Before (deadlock-prone):
def transfer_money(from_account, to_account, amount):
    start_transaction()
    update_account(from_account, -amount)  # Locks from_account
    update_account(to_account, +amount)    # Then locks to_account
    commit()

# After (deadlock-safe):
def transfer_money(from_account, to_account, amount):
    # Always lock in same order: lower ID first
    first = min(from_account, to_account)
    second = max(from_account, to_account)
    
    start_transaction()
    lock_account(first)   # Always lock smaller ID first
    lock_account(second)  # Then larger ID
    # Perform updates...
    commit()
```

### Fix: Use SELECT FOR UPDATE with Ordering
```sql
-- Before (may deadlock):
BEGIN;
UPDATE account SET balance = balance - 100 WHERE id = account_a;
UPDATE account SET balance = balance + 100 WHERE id = account_b;
COMMIT;

-- After (safe):
BEGIN;
SELECT * FROM account WHERE id IN (account_a, account_b) ORDER BY id FOR UPDATE;
UPDATE account SET balance = balance - 100 WHERE id = account_a;
UPDATE account SET balance = balance + 100 WHERE id = account_b;
COMMIT;
```

### Fix: Lower Transaction Isolation Level
```bash
# If application accepts eventual consistency
# Lower from REPEATABLE_READ to READ_COMMITTED
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SET SESSION transaction_isolation='READ-COMMITTED';"

# This reduces lock scope and likelihood of deadlock
# But loses some consistency guarantees

# Set in my.cnf for all sessions
transaction-isolation=READ-COMMITTED

# Restart MySQL
kubectl rollout restart statefulset/<mysql-statefulset> -n <namespace>
```

### Implement Retry Logic in Application
```python
# Add exponential backoff retry for deadlock
def execute_with_retry(query, max_retries=3):
    for attempt in range(max_retries):
        try:
            execute_transaction(query)
            return True
        except DeadlockError:
            if attempt < max_retries - 1:
                sleep(2 ** attempt)  # Exponential backoff
                continue
            raise

# Call with retry
try:
    execute_with_retry(transfer_query)
except DeadlockError:
    log_error("Transfer failed after retries")
```

## Validation
```bash
# No deadlock errors in error logs
kubectl logs <app-pod> -n <namespace> | grep -i "deadlock" | wc -l

# Should be close to 0 after fix

# Transaction success rate should increase
# Query monitoring system

# Lock wait times should decrease
kubectl exec <db-pod> -n <namespace> -- mysql -u root -e \
  "SHOW ENGINE INNODB STATUS\\G" | grep -i "wait"
```

## Prevention
- Always lock tables/rows in consistent order
- Keep transactions short (minimize lock duration)
- Use appropriate isolation level
- Index columns used in WHERE clauses
- Avoid mixing transactional and non-transactional queries
- Implement retry logic with exponential backoff
- Monitor for deadlock frequency
- Load test concurrent scenarios
- Document transaction order in comments

## Severity
**P1** - Blocks critical transactions (payments, orders), requires immediate resolution.

## Escalation Matrix
| Frequency | Action |
|-----------|--------|
| < 1/day | Monitor |
| 1-5/day | Investigate lock ordering |
| > 5/day | Page developer, implement fix |
