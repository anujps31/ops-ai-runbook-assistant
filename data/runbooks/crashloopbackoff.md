# Kubernetes Pod CrashLoopBackOff Runbook

## Problem
A Kubernetes pod enters CrashLoopBackOff state, where the container crashes immediately after starting, causing the kubelet to retry with exponential backoff. This prevents the application from becoming available and impacts service reliability.

## Symptoms
1. Pod status shows `CrashLoopBackOff` in kubectl get pods
2. Pod restarts counter continuously increments (e.g., 5, 10, 20+ restarts)
3. Application logs show immediate termination errors
4. Container runtime events indicate Exit Code 1, 137, or 139
5. Service endpoints remain unavailable (no ready replicas)
6. Recent deployments fail to reach Ready state within timeout
7. Resource usage spikes followed by immediate container termination
8. Init containers complete but main container fails instantly
9. Volume mount failures prevent container startup
10. Configuration secrets/ConfigMaps referenced but not found

## Impact
- **Immediate**: Service degradation or complete outage for dependent applications
- **User-facing**: API calls fail with 503 Service Unavailable
- **SLA**: Potential SLA breach depending on service criticality
- **Data pipelines**: Batch jobs remain incomplete, delaying analytics

## Possible Root Causes
1. **Application crash**: Unhandled exception, segmentation fault, or runtime error
2. **Resource constraints**: Out of memory (OOMKilled), insufficient CPU
3. **Missing dependencies**: Required libraries, language runtime not available
4. **Configuration errors**: Invalid environment variables, missing secrets/ConfigMaps
5. **Health check failure**: Liveness probe configured too aggressively
6. **File system issues**: Read-only root filesystem, insufficient disk space in container
7. **Permission issues**: Container running as wrong user (security context mismatch)
8. **Entrypoint problems**: Shell script failure, incorrect command execution
9. **Network issues**: Pod cannot resolve DNS, cannot reach required service
10. **Image corruption**: Malformed Docker image, missing binary, incompatible layers

## Investigation Steps

### Step 1: Verify Pod Status and Basic Information
```bash
# Get detailed pod status
kubectl describe pod <pod-name> -n <namespace>

# Check pod events (most recent at bottom)
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | grep <pod-name>

# View pod YAML configuration
kubectl get pod <pod-name> -n <namespace> -o yaml
```

### Step 2: Examine Container Logs
```bash
# Get application logs from crashed container
kubectl logs <pod-name> -n <namespace>

# Get logs from previous container instance (if available)
kubectl logs <pod-name> -n <namespace> --previous

# Stream logs in real-time (if restarting)
kubectl logs -f <pod-name> -n <namespace>

# Get logs from all containers in pod
kubectl logs <pod-name> -n <namespace> --all-containers=true
```

### Step 3: Check for OOMKilled Status
```bash
# Get detailed termination reason
kubectl describe pod <pod-name> -n <namespace> | grep -A 5 "Last State"

# Check if Exit Code is 137 (OOMKilled signal)
# Exit 1 = application error
# Exit 137 = killed by signal 9 (SIGKILL from OOMKiller)
# Exit 139 = segmentation fault (signal 11)

# Check node resource pressure
kubectl describe node <node-name> | grep -A 5 "Conditions:"
```

### Step 4: Verify Configuration
```bash
# Check if ConfigMap exists and has correct data
kubectl get configmap <config-name> -n <namespace>
kubectl describe configmap <config-name> -n <namespace>

# Check if Secret exists and has correct keys
kubectl get secret <secret-name> -n <namespace>
kubectl describe secret <secret-name> -n <namespace>

# Verify environment variables reference correct names
kubectl set env pod <pod-name> -n <namespace> --list
```

### Step 5: Check Container Image
```bash
# Pull and inspect image locally
docker pull <image-registry>/<image-name>:<tag>

# Check image layers and history
docker history <image-registry>/<image-name>:<tag>

# Run image locally to test startup
docker run --rm -it <image-registry>/<image-name>:<tag> sh

# Verify binary/entrypoint exists in image
docker inspect <image-registry>/<image-name>:<tag> | grep -A 5 "Cmd"
```

### Step 6: Examine Security Context
```bash
# Check pod security context and user
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.securityContext}'

# Check if running as expected user (often must be non-root)
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.containers[0].securityContext}'

# Verify container can write to filesystem
kubectl exec <pod-name> -n <namespace> -- touch /tmp/test.txt && rm /tmp/test.txt
```

### Step 7: Test Liveness/Readiness Probes
```bash
# Get probe configuration
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.containers[0].livenessProbe}'

# Manually execute probe command
kubectl exec <pod-name> -n <namespace> -- /bin/sh -c "curl -f http://localhost:8080/health"

# Temporarily disable probe to allow container to run
kubectl set probe deployment/<deployment-name> -n <namespace> --liveness --initial-delay-seconds=300
```

### Step 8: Check Deployment Resource Limits
```bash
# View resource requests/limits
kubectl get deployment <deployment-name> -n <namespace> -o jsonpath='{.spec.template.spec.containers[0].resources}'

# Check node available resources
kubectl top node <node-name>
kubectl describe node <node-name> | grep -A 10 "Allocated resources"
```

### Step 9: Verify Volume Mounts
```bash
# Check if volumes are properly mounted
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.volumes}'

# Check if PVC/PV exists and is accessible
kubectl get pvc -n <namespace>
kubectl get pv | grep <pvc-name>

# Test volume permissions
kubectl exec <pod-name> -n <namespace> -- ls -la /mnt/volume/
```

### Step 10: Check Init Containers
```bash
# If pod uses init containers, verify they complete
kubectl describe pod <pod-name> -n <namespace> | grep -A 10 "Init Containers:"

# Get init container logs
kubectl logs <pod-name> -n <namespace> -c <init-container-name>

# Check init container exit code
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.initContainerStatuses[0].state}'
```

## Resolution Steps

### For Application Crashes
1. Review recent code changes in git:
   ```bash
   git log --oneline -20
   git diff HEAD~1 HEAD
   ```
2. Check for unhandled exceptions in application startup code
3. Verify all required environment variables are set
4. Test application locally with same environment variables
5. Rebuild image with debugging enabled
6. Deploy with verbose logging

### For OOMKilled
1. **Increase memory limit**:
   ```bash
   kubectl set resources deployment/<deployment-name> -n <namespace> --limits=memory=2Gi
   ```
2. Analyze memory usage patterns
3. Check for memory leaks in application code
4. Optimize image size to reduce overhead
5. Consider node scaling if multiple pods OOMKilled

### For Missing Configuration
1. Create missing ConfigMap:
   ```bash
   kubectl create configmap <config-name> --from-file=config.yaml -n <namespace>
   ```
2. Create missing Secret:
   ```bash
   kubectl create secret generic <secret-name> --from-literal=key=value -n <namespace>
   ```
3. Redeploy pod to pick up new configuration:
   ```bash
   kubectl rollout restart deployment/<deployment-name> -n <namespace>
   ```

### For Health Check Failures
1. Increase initial delay before first probe:
   ```bash
   kubectl patch deployment <deployment-name> -n <namespace> -p \
     '{"spec":{"template":{"spec":{"containers":[{"name":"<container-name>","livenessProbe":{"initialDelaySeconds":60}}]}}}}'
   ```
2. Verify application HTTP endpoint responds within timeout
3. Disable probe temporarily to debug:
   ```bash
   kubectl set probe deployment/<deployment-name> -n <namespace> --liveness --initial-delay-seconds=300 --timeout-seconds=10
   ```

## Validation
```bash
# Pod should reach Running state
kubectl get pod <pod-name> -n <namespace> --watch

# Pod ready replicas should equal desired
kubectl get deployment <deployment-name> -n <namespace>

# Logs should show successful startup
kubectl logs <pod-name> -n <namespace>

# Service endpoints should become available
kubectl get endpoints <service-name> -n <namespace>

# Application health check should pass
kubectl exec <pod-name> -n <namespace> -- curl -f http://localhost:8080/health
```

## Prevention
- Implement comprehensive startup tests in CI/CD pipeline
- Use multi-stage Docker builds to minimize image size and reduce attack surface
- Set appropriate resource requests/limits based on actual usage patterns
- Implement gradual startup with high initial-delay-seconds (60-120 seconds)
- Use init containers to validate all dependencies before main container starts
- Implement detailed application logging for startup sequence
- Perform load testing to identify memory leaks before production deployment
- Use liveness probe with high failure threshold (failureThreshold: 5) to avoid premature kills
- Automate image scanning for missing dependencies

## Severity
**P2** - High priority if impacting production services, requires immediate investigation and may escalate to P1 if affecting critical paths.

## Escalation Matrix
| Duration | Action |
|----------|--------|
| < 5 min | Engineer investigation |
| 5-15 min | Notify team lead |
| 15-30 min | Escalate to platform team |
| > 30 min | Declare P1 incident, page on-call manager |
| Repeated occurrence | Escalate to architecture/security team |
