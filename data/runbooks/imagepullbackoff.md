# Kubernetes ImagePullBackOff Runbook

## Problem
A Kubernetes pod cannot pull its container image from the registry, resulting in ImagePullBackOff state. The kubelet retries with exponential backoff, preventing pod startup and service availability.

## Symptoms
1. Pod status shows `ImagePullBackOff` or `ErrImagePull`
2. Pod events show "Failed to pull image: authentication required"
3. Pod remains in Pending state indefinitely
4. Image pull error mentions registry credentials or URL issues
5. Container image specification contains incorrect tag or registry path
6. Registry connectivity issues from cluster
7. Image manifest not found in registry
8. Pod EventReason: `Failed` with message referencing image pull
9. No container logs available (never started)
10. Docker image inspection locally succeeds but pull from pod fails

## Impact
- **Availability**: Pod unable to start, service remains unavailable
- **Deployment**: New rollouts fail to reach ready state
- **Scaling**: Horizontal pod autoscaler cannot add new replicas
- **Updates**: Configuration changes cannot be applied until image issue resolved
- **SLA**: Direct violation if production service affected

## Possible Root Causes
1. **Registry credentials missing**: ImagePullSecret not configured or expired
2. **Incorrect image path**: Wrong registry URL, namespace, or repository name
3. **Invalid image tag**: Tag doesn't exist, misspelled, or not pushed
4. **Registry unavailable**: Registry server down or unreachable from cluster
5. **Network policy**: Cluster cannot reach registry due to firewall rules
6. **Image too large**: Timeout during pull of massive image (>1GB)
7. **Expired credentials**: Docker credentials valid at deployment time but now expired
8. **Private registry**: Public registry configuration but image in private namespace
9. **Rate limiting**: Registry rate limits exceeded from cluster

## Investigation Steps

### Step 1: Check Pod Status and Events
```bash
# Get detailed pod status and pull events
kubectl describe pod <pod-name> -n <namespace>

# Events show most recent errors
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | grep <pod-name>

# Look for "Failed to pull image" events
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.conditions}'
```

### Step 2: Verify Image Name and Tag
```bash
# Check deployment image specification
kubectl get deployment <deployment-name> -n <namespace> -o jsonpath='{.spec.template.spec.containers[0].image}'

# Check pod image reference (may differ from deployment)
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.containers[0].image}'

# Verify image exists in registry (pull locally on administrator machine)
docker pull <registry>/<namespace>/<image>:<tag>

# Check image history and size
docker inspect <registry>/<namespace>/<image>:<tag>
```

### Step 3: Check ImagePullSecrets Configuration
```bash
# List configured image pull secrets
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.imagePullSecrets}'

# Verify secret exists
kubectl get secret <secret-name> -n <namespace>
kubectl get secret <secret-name> -n <namespace> -o jsonpath='{.data.\.dockercfg}'

# Check service account default image pull secrets
kubectl get serviceaccount <sa-name> -n <namespace> -o jsonpath='{.imagePullSecrets}'

# Verify secret is in same namespace as pod
kubectl get secrets -n <namespace> | grep docker
```

### Step 4: Test Registry Connectivity from Cluster
```bash
# Create a temporary pod to test registry access
kubectl run test-pull --image=<registry>/<namespace>/<image>:<tag> \
  -n <namespace> --image-pull-policy=IfNotPresent

# Test network connectivity to registry
kubectl run -it --rm debug --image=nicolaka/netshoot --restart=Never -- \
  curl -v https://<registry-host>/v2/

# Check DNS resolution from pod
kubectl exec <pod-name> -n <namespace> -- nslookup <registry-host>

# Test registry connectivity with telnet
kubectl run -it --rm debug --image=nicolaka/netshoot --restart=Never -- \
  telnet <registry-host> 443
```

### Step 5: Validate Docker Credentials
```bash
# Decode and inspect docker secret
kubectl get secret <secret-name> -n <namespace> -o jsonpath='{.data.\.dockerconfig\.json}' | base64 -d | jq .

# Check if credentials for registry exist in secret
kubectl get secret <secret-name> -n <namespace> -o jsonpath='{.data.\.dockerconfig\.json}' | base64 -d | jq '.auths | keys'

# Verify credentials match registry host exactly
# Registry host must match exactly (e.g., "docker.io" vs "registry.docker.io")
```

### Step 6: Check Registry Server Status
```bash
# From cluster admin node, test registry accessibility
curl -k https://<registry-host>/v2/

# Check registry certificate validity
openssl s_client -connect <registry-host>:443 -showcerts

# Query registry API for image manifest
curl -k -H "Authorization: Bearer $(curl -k https://<user>:<pass>@<registry>/token)" \
  https://<registry>/v2/<namespace>/<image>/manifests/<tag>

# Check docker log on registry server for pull attempts
docker logs <registry-container-name> | grep <image>
```

### Step 7: Examine Network Policies
```bash
# Check if network policies restrict registry access
kubectl get networkpolicies -n <namespace>
kubectl get networkpolicies -n <namespace> -o yaml

# Check for ingress policies blocking egress to registry
kubectl describe networkpolicy <policy-name> -n <namespace>

# Temporarily disable network policy to test
kubectl delete networkpolicy <policy-name> -n <namespace>
```

### Step 8: Check Kubelet Logs
```bash
# SSH to node where pod scheduled
ssh <node-ip>

# Check kubelet service status
systemctl status kubelet

# Check kubelet logs for image pull errors
journalctl -u kubelet -n 100 | grep -i "image"
journalctl -u kubelet -n 100 | grep -i "pull"

# Check containerd/docker logs
journalctl -u containerd -n 100 | grep -i "image"
```

### Step 9: Verify Image Manifest and Layers
```bash
# Inspect image in registry (requires authentication)
docker inspect <registry>/<namespace>/<image>:<tag>

# Check if image is actually pushed to registry
docker search <registry>/<image>

# Verify layer digests are correct
docker images --digests <registry>/<namespace>/<image>

# Check if image manifest is compatible with cluster architecture
# Ensure image is built for cluster architecture (amd64, arm64, etc.)
```

### Step 10: Check Certificate and SSL Issues
```bash
# Verify registry certificate
kubectl logs <pod-name> -n <namespace> || echo "No logs"

# Check if certificate validation is issue
# Might see "x509: certificate signed by unknown authority"

# Verify CA certificate is mounted in kubelet
cat /etc/kubernetes/pki/ca.crt

# Check if insecure registry configured
cat /etc/docker/daemon.json | grep -i "insecure"
```

## Resolution Steps

### For Missing/Incorrect ImagePullSecret
```bash
# Create docker registry secret if missing
kubectl create secret docker-registry <secret-name> \
  --docker-server=<registry-host> \
  --docker-username=<username> \
  --docker-password=<password> \
  --docker-email=<email> \
  -n <namespace>

# Patch deployment to use secret
kubectl patch deployment <deployment-name> -n <namespace> -p \
  '{"spec":{"template":{"spec":{"imagePullSecrets":[{"name":"<secret-name>"}]}}}}'

# Force pod restart to pick up new secret
kubectl rollout restart deployment/<deployment-name> -n <namespace>
```

### For Incorrect Image Path or Tag
```bash
# Update deployment image (fastest way)
kubectl set image deployment/<deployment-name> \
  <container-name>=<new-registry>/<namespace>/<image>:<new-tag> \
  -n <namespace>

# Verify rollout progresses without ImagePullBackOff
kubectl rollout status deployment/<deployment-name> -n <namespace>
```

### For Registry Unreachable
```bash
# If using private registry, ensure DNS resolves from cluster
kubectl run -it --rm debug --image=nicolaka/netshoot --restart=Never -- \
  nslookup <registry-host>

# If firewall issue, add firewall rules allowing egress to registry
# (Work with infrastructure team)

# If registry down, restore or switch to mirror registry
kubectl patch deployment <deployment-name> -n <namespace> -p \
  '{"spec":{"template":{"spec":{"containers":[{"name":"<container-name>","image":"<mirror-registry>/<image>:<tag>"}]}}}}'
```

### For Rate Limiting Issues
```bash
# Implement exponential backoff by adjusting imagePullPolicy
kubectl patch deployment <deployment-name> -n <namespace> -p \
  '{"spec":{"template":{"spec":{"containers":[{"name":"<container-name>","imagePullPolicy":"IfNotPresent"}]}}}}'

# Spread image pulls across multiple replicas over time
# Implement pod disruption budgets to prevent simultaneous reschedules
kubectl patch deployment <deployment-name> -n <namespace> -p \
  '{"spec":{"template":{"spec":{"terminationGracePeriodSeconds":120}}}}'
```

## Validation
```bash
# Pod should reach Running state
kubectl get pod <pod-name> -n <namespace> --watch

# Pod events should show successful pull
kubectl describe pod <pod-name> -n <namespace> | grep "Pulled image"

# Container should start successfully
kubectl logs <pod-name> -n <namespace> | head -20

# Deployment ready replicas should match desired
kubectl get deployment <deployment-name> -n <namespace>
```

## Prevention
- Maintain list of allowed registries and update firewall accordingly
- Implement CI/CD validation to verify image pushes complete
- Set image pull policy to `IfNotPresent` to reduce redundant pulls
- Refresh image pull secrets 30 days before expiration
- Use image digest pinning (SHA256) instead of tags for production
- Implement image scanning in registry to catch corruption
- Monitor registry availability and setup alerts
- Use local image cache/mirror for frequently used images
- Document registry host, namespace, and authentication requirements

## Severity
**P2** - Blocks deployment/scaling, requires immediate resolution to restore service availability.

## Escalation Matrix
| Duration | Action |
|----------|--------|
| < 5 min | Check image name/tag accuracy |
| 5-10 min | Verify registry connectivity |
| 10-20 min | Engage registry/infrastructure team |
| 20-30 min | Page on-call platform engineer |
| > 30 min | Escalate to infrastructure lead |
