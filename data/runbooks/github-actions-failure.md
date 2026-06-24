# GitHub Actions Failure Runbook

## Problem
GitHub Actions workflow fails, preventing deployment, testing, or other automated CI/CD processes. Pipeline is blocked and changes cannot be deployed.

## Symptoms
1. Workflow shows red X (failed) status
2. Build job fails with error message
3. Test suite fails unexpectedly
4. Deployment step times out
5. Specific step fails, others pass
6. Intermittent failures (flaky tests)
7. Recent code change caused failure
8. Workflow works locally but fails in CI
9. Secrets or credentials issue causing auth failure
10. Matrix job fails on specific runner/config

## Possible Root Causes
1. **Code error**: Recent change broke test/build
2. **Flaky test**: Test fails intermittently
3. **Resource unavailable**: Service/database not available
4. **Timeout**: Operation takes longer than timeout
5. **Credentials expired**: API keys, tokens, secrets invalid
6. **Dependency issue**: Package version conflict
7. **Runner issue**: GitHub runner out of memory/disk
8. **Network issue**: Cannot reach external service
9. **Permission issue**: No access to deploy/publish
10. **Configuration error**: Workflow YAML syntax error

## Investigation Steps

### Step 1: Check Workflow Status
```bash
# View workflow runs
gh run list --limit 10

# Get detailed status of failed run
gh run view <run-id>

# Get logs of failed job
gh run view <run-id> --log

# Check specific step logs
gh run view <run-id> --log | grep -A 30 "<step-name>"

# Download full logs
gh run view <run-id> --log > workflow.log
```

### Step 2: Review Recent Code Changes
```bash
# Check git log for recent commits
git log --oneline -10

# See what changed in failed test
git diff HEAD~1 -- <test-file>

# See what changed in failed build
git diff HEAD~1 -- <source-file>

# Check if this specific change causes failure
git revert HEAD
git push  # Temporarily revert to test
```

### Step 3: Check Workflow Configuration
```bash
# Review workflow file
cat .github/workflows/<workflow>.yml

# Check for syntax errors
github-cli --validate .github/workflows/<workflow>.yml

# Or manually verify YAML
python -m yaml .github/workflows/<workflow>.yml

# Look for:
# - Incorrect action versions
# - Missing required inputs
# - Typos in secret names
# - Incorrect if: conditions
```

### Step 4: Run Test Locally
```bash
# Replicate CI environment locally

# Install dependencies
npm install  # or equivalent

# Run specific failing test
npm test -- --testNamePattern="failing test"

# Or build command
npm run build

# If succeeds locally, likely environment difference
```

### Step 5: Check for Secrets/Credentials Issues
```bash
# View workflow to see which secrets used
grep "secrets\." .github/workflows/<workflow>.yml

# Verify secrets are set in repository
gh secret list

# Check if specific secret exists
gh secret list | grep <SECRET_NAME>

# If missing, add it
gh secret set <SECRET_NAME> < secret-value.txt

# Check expiration of API keys/tokens
# Usually tokens valid for 1 year
```

### Step 6: Check Action Versions
```bash
# Review actions being used
grep "uses:" .github/workflows/<workflow>.yml

# Check for version pins
# Example: actions/checkout@v3 vs actions/checkout@main

# Verify action still exists
curl https://github.com/<owner>/<action>/releases

# If version deprecated or removed, update
sed -i 's/@v2/@v3/g' .github/workflows/<workflow>.yml
```

### Step 7: Check for Timeouts
```bash
# Look for timeout in workflow logs
grep -i "timeout\|timed out" workflow.log

# Check configured job timeout
grep "timeout-minutes:" .github/workflows/<workflow>.yml

# If step taking longer than timeout, increase it
sed -i 's/timeout-minutes: 10/timeout-minutes: 30/' .github/workflows/<workflow>.yml

# Or optimize slow step to complete faster
```

### Step 8: Check Runner Status
```bash
# Check if runner out of resources
# In GitHub UI: Settings > Actions > Runners

# Or via CLI
gh api repos/<owner>/<repo>/actions/runners

# If runner runner shows last_sync_at very old, runner down

# Check runner logs (if self-hosted)
ssh <runner-host>
journalctl -u actions.runner -n 50
tail -50 /var/log/actions-runner.log
```

### Step 9: Check Dependency Versions
```bash
# Check package-lock.json or yarn.lock
git log -p -- package-lock.json | head -50

# If recently updated, might have breaking change

# Pin to known-good version
npm install <package>@<specific-version>
git commit -am "Pin dependency version"

# Or check if dependency issue
npm audit

# Fix vulnerabilities
npm audit fix
```

### Step 10: Test Manually with Act
```bash
# Use act to run workflow locally
act push

# Or specific job
act push -j build

# Or specific event
act pull_request

# Act simulates GitHub Actions environment locally
# Can debug without pushing to GitHub

# Install act: https://github.com/nektos/act

# Run specific workflow
act -W .github/workflows/<workflow>.yml
```

## Resolution Steps

### For Code Error: Fix and Commit
```bash
# Identify failing test/build
# Fix the issue in code

# Test locally
npm test

# Commit and push
git add .
git commit -m "Fix failing test"
git push

# GitHub Actions will retry automatically
```

### For Flaky Test: Add Retry or Fix
```bash
# Add retry logic
npm test -- --maxWorkers=1 --forceExit

# Or use jest-circus for better error handling
npm install --save-dev @testing-library/jest-dom

# Or skip flaky test temporarily
# Add .skip() to specific test
it.skip('flaky test', () => {...})

# Fix root cause of flakiness
# Usually: timing issue, network dependency, race condition
```

### For Timeout: Increase or Optimize
```bash
# Increase job timeout
timeout-minutes: 60  # Changed from 30

# Or split into parallel jobs
strategy:
  matrix:
    shard: [1, 2, 3]

# Or optimize slow step:
# - Use cache for dependencies
# - Parallel test execution
# - Skip unnecessary steps

# Add to workflow:
- uses: actions/cache@v3
  with:
    path: node_modules
    key: ${{ runner.os }}-node-${{ hashFiles('package-lock.json') }}
```

### For Missing Secrets: Add to Repository
```bash
# Add secret via GitHub CLI
gh secret set SECRET_NAME < secret-value.txt

# Or via GitHub UI:
# Settings > Secrets and variables > Actions > New repository secret

# Then reference in workflow:
env:
  SECRET: ${{ secrets.SECRET_NAME }}

# Verify in workflow logs (should show as ***)
# Never log actual secret value
```

### For Failed Deployment: Check Permissions
```bash
# Verify deployer has permission
# Check RBAC/IAM for deployment target

# For Kubernetes:
kubectl auth can-i create deployments --as=system:serviceaccount:default:deployer

# For AWS:
aws iam get-user --user-name ci-deployer

# If missing permissions, grant them
kubectl create rolebinding deployer-admin --clusterrole=cluster-admin --serviceaccount=default:deployer
```

### For Network Issue: Add Retry
```bash
# Add retry logic to workflow
- name: Deploy
  run: |
    for i in {1..3}; do
      if ./deploy.sh; then
        break
      fi
      sleep 10
    done

# Or use action that supports retry:
- uses: nick-invision/retry@v2
  with:
    timeout_minutes: 10
    max_attempts: 3
    command: ./deploy.sh
```

## Validation
```bash
# Workflow should pass
gh run view <run-id> | grep "status:"
# Should show: ✓ passed

# All jobs should succeed
gh run view <run-id> --json jobs

# No error logs
gh run view <run-id> --log | grep -i "error" | wc -l

# Deployment should be live
curl https://<deployed-app>
```

## Prevention
- Test locally before pushing (run act)
- Pin dependency versions
- Add timeout margins (don't make too tight)
- Use matrix strategy for parallel testing
- Cache dependencies to speed up CI
- Add retry for network-dependent operations
- Rotate secrets/tokens regularly
- Monitor workflow execution times
- Test workflow changes in PR first
- Document secrets and environment setup

## Severity
**P2** - Blocks deployments, team productivity impacted.

## Escalation Matrix
| Impact | Action |
|--------|--------|
| CI only | Fix code, push again |
| Blocking deploy | Investigate immediately |
| Persistent | Page developer |
| Production rollout blocked | Page oncall manager |
