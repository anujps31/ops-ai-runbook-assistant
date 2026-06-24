# Ingress 502 Bad Gateway Runbook

## Problem
Ingress controller returns HTTP 502 Bad Gateway, indicating backend services are unreachable or unresponsive. Requests cannot be routed to healthy pods.

## Symptoms
1. Ingress returns 502 Bad Gateway status
2. Response headers show: "upstream timed out", "connection refused"
3. Specific paths or services fail with 502
4. Some replicas working, others failing (partial availability)
5. 502 errors spike during load
6. Ingress controller logs show timeout errors
7. Backend pods Running but marked as NotReady
8. Service endpoints empty or reduced
9. Readiness probes failing on backend
10. Connection reset before response from backend

## Possible Root Causes
1. **Backend pod crashed**: Pod terminating or crashing
2. **Readiness probe failure**: Pod marked NotReady by kubelet
3. **Backend unresponsive**: Application hung or slow
4. **Connection limits**: Too many concurrent connections
5. **Resource exhaustion**: Backend out of memory or CPU
6. **Network path broken**: Network policy or firewall blocking
7. **Ingress controller issue**: Controller pod down/restarting
8. **Service endpoint missing**: No healthy endpoints registered
9. **Port mismatch**: Service port differs from container port
10. **Timeout too aggressive**: Ingress timeout < backend response time

## Investigation Steps

### Step 1: Check Backend Pod Status
```bash
# Get pods backing the service
kubectl get pods -n <namespace> -l app=<service-label>

# Describe pods for events and readiness status
kubectl describe pod <pod-name> -n <namespace> | grep -A 5 "Ready\|Conditions"

# Check if pods are actually Running
kubectl get pods -n <namespace> -o wide | grep <service>

# Count ready replicas
kubectl get deployment <deployment> -n <namespace> | grep <service>
```

### Step 2: Test Readiness Probes
```bash
# Check readiness probe configuration
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.containers[0].readinessProbe}' | jq .

# Manually test readiness endpoint
kubectl exec <pod-name> -n <namespace> -- curl -f http://localhost:8080/health

# Check probe history
kubectl describe pod <pod-name> -n <namespace> | grep -A 10 "Readiness"

# If HTTP probe, check response code
kubectl exec <pod-name> -n <namespace> -- curl -v http://localhost:8080/health 2>&1 | grep "< HTTP"

# Check probe logs
kubectl logs <pod-name> -n <namespace> | grep -i "health\|ready" | tail -20
```

### Step 3: Check Service Endpoints
```bash
# Get service endpoints
kubectl get endpoints <service> -n <namespace>

# Should show IP:port of backing pods
# If empty or reduced, pods are NotReady or service selector incorrect

# Verify service selector matches pod labels
kubectl get service <service> -n <namespace> -o yaml | grep -A 5 "selector:"

# Check pod labels
kubectl get pods -n <namespace> <pod> -o yaml | grep -A 3 "labels:"

# Manually check if selector matches
kubectl get pods -n <namespace> -l <label>=<value>
```

### Step 4: Check Ingress Configuration
```bash
# Get ingress resource
kubectl get ingress -n <namespace> -o yaml

# Verify backend service name and port
kubectl get ingress <ingress-name> -n <namespace> -o jsonpath='{.spec.rules[0].http.paths[0].backend}' | jq .

# Check if service port name is used correctly
kubectl get service <service> -n <namespace> -o yaml | grep -A 5 "ports:"

# Check ingress class (might be wrong controller)
kubectl get ingress <ingress-name> -n <namespace> -o jsonpath='{.spec.ingressClassName}'
```

### Step 5: Check Ingress Controller Status
```bash
# Get ingress controller pod
kubectl get pods -n ingress-nginx

# Check controller logs for errors
kubectl logs -n ingress-nginx -l app=ingress-nginx -n ingress-nginx | tail -50

# Look for 502 errors
kubectl logs -n ingress-nginx | grep "502\|upstream.*timeout"

# Check controller resource usage
kubectl top pod -n ingress-nginx -l app=ingress-nginx

# Verify controller is actually processing ingress
kubectl logs -n ingress-nginx | grep <ingress-name>
```

### Step 6: Test Backend Connectivity
```bash
# SSH from ingress controller to backend service
kubectl exec -it <ingress-controller-pod> -n ingress-nginx -- bash

# Test from inside controller
curl -v http://<service>:8080/health

# Or test from another pod in same namespace
kubectl run -it --rm curl --image=curlimages/curl --restart=Never -- \
  curl -v http://<service>.<namespace>.svc.cluster.local:8080/

# Test specific pod directly (bypassing service)
kubectl run -it --rm curl --image=curlimages/curl --restart=Never -- \
  curl -v http://<pod-ip>:8080/
```

### Step 7: Check Application Logs
```bash
# Get backend application logs
kubectl logs <pod-name> -n <namespace> | tail -50

# Look for startup errors
kubectl logs <pod-name> -n <namespace> --previous

# Check for high latency or timeouts
kubectl logs <pod-name> -n <namespace> | grep -i "timeout\|slow"

# Check for exceptions
kubectl logs <pod-name> -n <namespace> | grep -i "error\|exception"
```

### Step 8: Check Resource Usage of Backend
```bash
# Get backend pod resource usage
kubectl top pod <pod-name> -n <namespace>

# Check if near limits
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.containers[0].resources}'

# Check if OOMKilled
kubectl describe pod <pod-name> -n <namespace> | grep -i "oomkilled\|memory"

# Get CPU and memory charts over time (requires monitoring)
# Query Prometheus: rate(container_cpu_usage_seconds_total[5m])
# Query Prometheus: container_memory_rss_bytes
```

### Step 9: Check Connection Limits
```bash
# Check if connection pool exhausted
kubectl logs <pod-name> -n <namespace> | grep -i "connection.*exhaust\|too many*connect"

# Check open connections
kubectl exec <pod-name> -n <namespace> -- ss -an | grep ESTABLISHED | wc -l

# Check max connections limit
kubectl exec <pod-name> -n <namespace> -- ss -an | head -2

# Check application connection pool configuration
kubectl get configmap <app-config> -n <namespace> -o yaml | grep -i "max.*connect"
```

### Step 10: Check Ingress Timeout Settings
```bash
# Get ingress controller configuration
kubectl get configmap nginx-configuration -n ingress-nginx -o yaml

# Check timeout settings
kubectl get configmap nginx-configuration -n ingress-nginx -o yaml | grep -i "timeout"

# Check if specific backend needs longer timeout
# proxy-connect-timeout default: 5s
# proxy-send-timeout default: 60s
# proxy-read-timeout default: 60s

# Check backend response time
kubectl logs <pod-name> -n <namespace> | grep -i "response.*time\|latency"
```

## Resolution Steps

### If Backend Pod Crashed: Restart
```bash
# Delete pod (deployment will recreate)
kubectl delete pod <pod-name> -n <namespace>

# Monitor restart
kubectl get pod <pod-name> -n <namespace> --watch

# Check logs
kubectl logs <pod-name> -n <namespace>
```

### If Readiness Probe Failing: Increase Delays
```bash
# Temporarily disable readiness probe to debug
kubectl set probe deployment/<deployment> -n <namespace> \
  --readiness --initial-delay-seconds=300 --failure-threshold=10

# Or fix underlying issue first, then restart
kubectl rollout restart deployment/<deployment> -n <namespace>
```

### If No Endpoints: Fix Service Selector
```bash
# Verify service selector
kubectl get svc <service> -n <namespace> -o yaml | grep -A 5 "selector"

# Add/fix labels on pods if needed
kubectl label pods <pod-name> -n <namespace> app=<service-label> --overwrite

# Or update service selector
kubectl patch svc <service> -n <namespace> -p \
  '{"spec":{"selector":{"app":"<label>"}}}'

# Verify endpoints appear
kubectl get endpoints <service> -n <namespace>
```

### If Backend Slow: Increase Timeout
```bash
# Update ingress timeout annotation
kubectl patch ingress <ingress-name> -n <namespace> -p \
  '{"metadata":{"annotations":{"nginx.ingress.kubernetes.io/proxy-read-timeout":"120"}}}'

# Or update controller ConfigMap
kubectl patch configmap nginx-configuration -n ingress-nginx -p \
  '{"data":{"proxy-read-timeout":"120"}}'

# Reload controller
kubectl rollout restart deployment/nginx-ingress-controller -n ingress-nginx
```

### If Resource Exhausted: Scale Up or Increase Limits
```bash
# Scale up backend replicas
kubectl scale deployment/<deployment> --replicas=5 -n <namespace>

# Or increase resource limits
kubectl set resources deployment/<deployment> \
  -n <namespace> \
  --limits=memory=2Gi,cpu=1000m

# Redeploy
kubectl rollout restart deployment/<deployment> -n <namespace>
```

## Validation
```bash
# Ingress should return 200 OK
curl -I https://<ingress-host>

# Service should have endpoints
kubectl get endpoints <service> -n <namespace>

# Pods should be Ready
kubectl get pods -n <namespace> | grep <service>

# No 502 errors in ingress logs
kubectl logs -n ingress-nginx | grep "502" | tail -5
```

## Prevention
- Set readiness probe initial delay to allow startup (30-60 sec)
- Implement gradual startup in application
- Monitor backend response times continuously
- Right-size resource limits based on actual usage
- Load test before production deployment
- Use separate ingress instances for critical services
- Implement circuit breaker at application level
- Monitor ingress controller resource usage
- Set up alerts for 502 spike

## Severity
**P1** - Blocks user access, immediate investigation needed.

## Escalation Matrix
| Scope | Action |
|-------|--------|
| Single pod | Restart pod, check logs |
| All replicas | Check readiness probe, service selector |
| All services | Check ingress controller status |
| > 5 min | Page on-call engineer |
