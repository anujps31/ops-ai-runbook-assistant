# Terraform State Lock Runbook

## Problem
Terraform state lock remains held after operation completes or crashes, preventing future operations. Terraform waits indefinitely for lock release or uses `-force-unlock` risking state corruption.

## Symptoms
1. Terraform operations timeout waiting for lock
2. Lock acquired hours ago by crashed process
3. Error: "Error acquiring the lock: context deadline exceeded"
4. `.terraform.lock.hcl` file exists but stale
5. Specific workspace locked
6. Cannot apply, plan, or destroy
7. Lock owner process no longer running
8. Remote state backend shows held lock
9. Multiple engineers unable to coordinate
10. Lock release requires manual intervention

## Impact
- **Deployment blocked**: Cannot apply infrastructure changes
- **Incidents prolonged**: Cannot adjust resources during incident
- **Team blocked**: All engineers unable to make changes
- **State risk**: Force unlock risks state corruption

## Possible Root Causes
1. **Crashed terraform process**: Process died before releasing lock
2. **Long-running operation**: Lock held > default timeout
3. **Network disconnect**: Terraform lost connectivity mid-operation
4. **Process killed**: SIGKILL before cleanup code ran
5. **Stale lock**: Previous operation completed but lock not released
6. **Backend issue**: Lock store unreachable or corrupted
7. **Lock holder unknown**: Different pod/container acquired lock
8. **Permission issue**: Cannot release lock due to RBAC
9. **Lock ID mismatch**: Recorded lock ID differs from actual lock
10. **Multiple workers**: Multiple Terraform instances running simultaneously

## Investigation Steps

### Step 1: Check Terraform Lock Status
```bash
# Check if .terraform.lock.hcl exists
ls -lh .terraform.lock.hcl

# Check lock file contents
cat .terraform.lock.hcl

# Check lock age (when it was created)
stat .terraform.lock.hcl | grep "Modify:"

# Check lock holder PID (if local state)
cat .terraform/.terraform.lock.hcl
```

### Step 2: Check Remote Backend Lock
```bash
# For S3 backend
aws dynamodb get-item \
  --table-name terraform-lock \
  --key '{"LockID": {"S": "<lock-id>"}}'

# Check lock age
# Date should be recent if still in use
# If old (> 1 hour), likely stale

# For Terraform Cloud backend
terraform login
terraform state list

# For local backend with http
curl https://<backend-host>/locks
```

### Step 3: Check Terraform Process Status
```bash
# SSH to Terraform execution host
ssh <terraform-host>

# Check for terraform processes
ps aux | grep terraform

# If running: terraform state lock acquired
# If not running: lock should be released (but might be stuck)

# Check process start time
ps -eo comm,etime | grep terraform

# If etime > 1 hour, process likely stuck
```

### Step 4: Check Kubernetes Context
```bash
# If Terraform runs in pod:

# Find terraform pod
kubectl get pods --all-namespaces | grep terraform

# Check pod status
kubectl describe pod <terraform-pod> -n <namespace>

# Check if pod was killed
kubectl get pod <terraform-pod> -n <namespace> -o jsonpath='{.status.containerStatuses[0].state}'

# If Terminated/Error, process was killed

# Check pod logs
kubectl logs <terraform-pod> -n <namespace> | tail -50

# Look for error at end (likely where lock was held)
```

### Step 5: Check Lock Owner Identity
```bash
# Check lock metadata
# Contains: "Operation": "apply", "Who": "user@host", "Version": "1.2.3"

# Verify if that user/process is still running
ps aux | grep "<who>"

# If not running, lock can be safely released

# Check if lock holder in same pod/container
kubectl exec <terraform-pod> -n <namespace> -- ps aux | grep terraform
```

### Step 6: Check Backend Connectivity
```bash
# Test backend access from terraform host

# For S3 backend
aws dynamodb describe-table --table-name terraform-lock

# For HTTP backend
curl -v https://<backend-host>/health

# For Consul
curl http://<consul-host>:8500/v1/status/leader

# Backend must be accessible for lock release
```

### Step 7: Check Terraform Logs
```bash
# Get recent terraform logs
cat terraform.log | tail -100

# Or enable debug logging
TF_LOG=DEBUG terraform plan 2>&1 | tail -50

# Look for lock acquisition/release messages
# "Acquiring state lock" / "Released state lock"

# Check if lock acquired but never released
grep -i "lock" terraform.log
```

### Step 8: Check Workspace Status
```bash
# Show current workspace
terraform workspace show

# List all workspaces
terraform workspace list

# Check if specific workspace locked
terraform workspace select <workspace>

# Try plan (will show lock error if still held)
terraform plan 2>&1 | head -20
```

### Step 9: Investigate Previous Operation
```bash
# Check terraform history/logs
ls -lh tfstate

# Check recent file modifications
ls -lht | head -20

# Review git history for terraform operations
git log --oneline -20 -- terraform/

# See what was being applied
git diff HEAD~1 -- terraform/
```

### Step 10: Check for Multiple Terraform Instances
```bash
# Check if multiple terraform processes running
ps aux | grep terraform | grep -v grep

# Check for terraform in CI/CD pipeline
# Jenkins: Check running jobs
# GitHub Actions: Check workflow runs
# GitLab CI: Check pipeline runs

# If multiple running simultaneously, one waits for lock
```

## Resolution Steps

### Option 1: Wait for Process to Complete (Safest)
```bash
# If terraform process running, wait for it to finish
ps aux | grep terraform

# Monitor process end time
watch -n 5 'ps aux | grep terraform | grep -v grep'

# Once process exits, lock releases automatically
# After 5 minutes, try terraform again
terraform plan

# Should succeed now
```

### Option 2: Kill Stuck Process Gracefully (Recommended)
```bash
# If terraform process stuck (> 1 hour):

# Send SIGTERM (graceful shutdown)
kill -TERM <pid>

# Wait 10 seconds
sleep 10

# Check if still running
ps aux | grep <pid>

# If still running, send SIGKILL (forced)
kill -KILL <pid>

# Now unlock (see below)
```

### Option 3: Release Lock from Backend
```bash
# For S3 backend (AWS)
aws dynamodb delete-item \
  --table-name terraform-lock \
  --key '{"LockID": {"S": "<lock-id>"}}'

# For Terraform Cloud
terraform login
terraform force-unlock <lock-id>

# For Consul
curl -X DELETE http://<consul-host>:8500/v1/kv/terraform/locks/<lock-id>

# Verify lock released
terraform plan  # Should no longer block
```

### Option 4: Force Unlock (Last Resort)
```bash
# WARNING: Only if absolutely sure no process holding lock

# Get lock ID
terraform state list

# Force unlock
terraform force-unlock <lock-id>

# This immediately releases lock
# But if terraform process still running, corruption risk

# After force unlock, check state integrity
terraform state list
terraform validate
```

### Option 5: Manual Lock File Removal (Local Backend)
```bash
# If using local backend:

# Check lock file
cat .terraform/.terraform.lock.hcl

# Remove lock file (if certain no process running)
rm .terraform/.terraform.lock.hcl

# Verify gone
ls .terraform/.terraform.lock.hcl  # Should error

# Try terraform again
terraform plan
```

### Prevention Going Forward
```bash
# Add lock timeout to terraform config
terraform_backend_s3_lock_table_timeout = 10

# Add pre-flight check in CI/CD
terraform state list > /dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "State is locked, aborting deployment"
  exit 1
fi

# Monitor lock age
aws dynamodb scan --table-name terraform-lock | jq '.Items[] | .LockTime'
```

## Validation
```bash
# Lock should be released
terraform plan
# Should succeed, not timeout

# Verify state readable
terraform state list

# Verify state valid
terraform validate

# Run without lock
terraform apply -auto-approve

# Lock should work normally going forward
# New lock created for this operation
# Then released when complete
```

## Prevention
- Always run terraform in containers with resource limits
- Set reasonable operation timeouts (30 min)
- Implement locking in CI/CD pipeline
- Monitor lock age with alerts > 30 min
- Use terraform cloud with managed state locking
- Centralize terraform runs in CI/CD (not local)
- Use workspace isolation
- Implement pre-apply lock checks
- Document lock release procedures for team
- Regular state backup for recovery

## Severity
**P2** - Blocks infrastructure changes, team productivity impacted.

## Escalation Matrix
| Lock Age | Action |
|----------|--------|
| < 30 min | Wait, monitor terraform process |
| 30-60 min | Investigate terraform process status |
| > 60 min | Kill process, release lock |
| Unknown owner | Force unlock as last resort |
