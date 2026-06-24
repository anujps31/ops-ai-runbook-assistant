# DNS Resolution Failure Runbook

## Problem
Pods cannot resolve DNS names, causing service discovery failures and broken inter-service communication. Applications timeout trying to reach services by hostname.

## Symptoms
1. DNS lookup fails: "Name or service not known", "Temporary failure in name resolution"
2. Service discovery broken - pods cannot find each other
3. External DNS (google.com) works but cluster DNS doesn't
4. CoreDNS pod not responding or restarting
5. Specific service unreachable but IP works
6. /etc/resolv.conf shows wrong nameserver
7. DNS queries timeout after 30-60 seconds
8. High latency on DNS queries (1-5 seconds)
9. Some pods can resolve, others cannot
10. Application logs show "getaddrinfo" failures

## Possible Root Causes
1. **CoreDNS down**: Pod crashed or not running
2. **Service not found**: Service doesn't exist or wrong namespace
3. **Network policy**: Egress policy blocks DNS traffic (port 53)
4. **CoreDNS configmap corrupted**: Configuration broken
5. **Kubelet incorrect**: Kubelet option points to wrong DNS server
6. **High DNS load**: Too many queries overwhelming CoreDNS
7. **DNS cache issues**: Stale entries or cache conflict
8. **Firewall blocking**: Egress firewall blocking port 53
9. **RBAC issue**: CoreDNS cannot access Kubernetes API
10. **Resource exhaustion**: CoreDNS CPU/memory limited

## Investigation Steps

### Step 1: Verify DNS Service Running
```bash
# Check CoreDNS pods
kubectl get pods -n kube-system -l k8s-app=kube-dns

# Check pod status
kubectl describe pod <coredns-pod> -n kube-system | grep -A 5 "Conditions\|Ready"

# Check CoreDNS service
kubectl get svc -n kube-system | grep dns

# Get DNS service IP (usually 10.96.0.10)
kubectl get svc kube-dns -n kube-system -o jsonpath='{.spec.clusterIP}'
```

### Step 2: Test DNS Resolution Inside Cluster
```bash
# Test from a pod
kubectl run -it --rm dnstools --image=tutum/dnsutils --restart=Never -- \
  nslookup kubernetes.default

# Test service in same namespace
kubectl run -it --rm dnstools --image=tutum/dnsutils --restart=Never -- \
  nslookup <service>

# Test service in different namespace
kubectl run -it --rm dnstools --image=tutum/dnsutils --restart=Never -- \
  nslookup <service>.<namespace>.svc.cluster.local

# Test external DNS
kubectl run -it --rm dnstools --image=tutum/dnsutils --restart=Never -- \
  nslookup google.com
```

### Step 3: Check CoreDNS Logs
```bash
# Get CoreDNS logs
kubectl logs -n kube-system -l k8s-app=kube-dns | tail -50

# Look for errors
kubectl logs -n kube-system -l k8s-app=kube-dns | grep -i "error\|fail"

# Check for RBAC errors (403 Forbidden)
kubectl logs -n kube-system -l k8s-app=kube-dns | grep -i "forbidden\|unauthorized"

# Check for connection refused (API server unreachable)
kubectl logs -n kube-system -l k8s-app=kube-dns | grep -i "connection.*refused"
```

### Step 4: Verify CoreDNS Configuration
```bash
# Get CoreDNS configmap
kubectl get configmap coredns -n kube-system -o yaml

# Check if Corefile is present and valid
kubectl get configmap coredns -n kube-system -o jsonpath='{.data.Corefile}'

# Verify nameserver entry for cluster.local
# Should see: "cluster.local" block with plugin configuration

# Check for corrupted YAML
kubectl get configmap coredns -n kube-system -o yaml | grep -A 20 "data:"
```

### Step 5: Check DNS Traffic from Pods
```bash
# Verify pods are using correct DNS server
kubectl exec <pod> -n <namespace> -- cat /etc/resolv.conf

# Should show: nameserver 10.96.0.10 (or configured DNS IP)
# Should have: search <namespace>.svc.cluster.local svc.cluster.local ...

# Check if DNS queries are reaching CoreDNS
kubectl exec <coredns-pod> -n kube-system -- cat /proc/net/netstat | grep -i "udp"

# Monitor incoming queries
kubectl exec <coredns-pod> -n kube-system -- tcpdump -i any port 53
```

### Step 6: Check Network Policies
```bash
# Get network policies that might block DNS
kubectl get networkpolicies -A | grep -v "^NAMESPACE.*NAME"

# Check if any policy blocks port 53 (DNS)
kubectl describe networkpolicy <policy> -n <namespace> | grep -i "53\|dns"

# Check egress policies (most likely culprit)
kubectl get networkpolicies -n <namespace> -o yaml | grep -A 10 "egress:"

# Test by temporarily deleting policy
kubectl delete networkpolicy <policy> -n <namespace>
# Test DNS, then reapply
```

### Step 7: Check CoreDNS Resource Usage
```bash
# Get CoreDNS resource usage
kubectl top pod -n kube-system -l k8s-app=kube-dns

# Check resource limits
kubectl get pod <coredns-pod> -n kube-system -o jsonpath='{.spec.containers[0].resources}'

# Check if CPU throttled
kubectl exec <coredns-pod> -n kube-system -- cat /sys/fs/cgroup/cpu/cpu.stat

# If high usage, reduce DNS queries or increase replicas
```

### Step 8: Verify Kubelet Configuration
```bash
# SSH to node
ssh <node-ip>

# Check kubelet DNS configuration
grep -i "cluster-dns\|cluster-domain" /etc/systemd/system/kubelet.service.d/10-kubeadm.conf

# Should show: --cluster-dns=10.96.0.10 --cluster-domain=cluster.local

# Check if kubelet service running
systemctl status kubelet

# Restart kubelet to apply changes if needed
sudo systemctl restart kubelet
```

### Step 9: Check RBAC for CoreDNS
```bash
# Check CoreDNS service account
kubectl get sa -n kube-system coredns

# Check role bindings
kubectl get rolebindings -n kube-system | grep coredns

# Get detailed RBAC config
kubectl describe clusterrole system:coredns

# If RBAC issue (403 errors), fix permissions:
kubectl apply -f - <<EOF
kind: ClusterRole
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: system:coredns
rules:
- apiGroups: [""]
  resources: ["endpoints", "services", "pods", "namespaces"]
  verbs: ["list", "watch"]
EOF
```

### Step 10: Monitor DNS Query Time
```bash
# Measure DNS query time
time kubectl run -it --rm dnstools --image=tutum/dnsutils --restart=Never -- \
  nslookup <service>

# Should complete in < 1 second
# If > 1 second, DNS is slow

# Check DNS cache hit rate
kubectl logs -n kube-system -l k8s-app=kube-dns | grep -i "cache"

# Monitor query patterns
kubectl logs -n kube-system -l k8s-app=kube-dns | grep "answer" | tail -20
```

## Resolution Steps

### If CoreDNS Crashed: Restart
```bash
# Delete CoreDNS pod (deployment will recreate)
kubectl delete pod -n kube-system -l k8s-app=kube-dns

# Monitor restart
kubectl get pods -n kube-system -l k8s-app=kube-dns --watch

# Check logs after restart
kubectl logs -n kube-system -l k8s-app=kube-dns
```

### If Network Policy Blocking: Update Policy
```bash
# Add DNS exception to network policy
kubectl patch networkpolicy <policy> -n <namespace> -p \
  '{"spec":{"egress":[{"to":[{"namespaceSelector":{"matchLabels":{"name":"kube-system"}}}],"ports":[{"protocol":"UDP","port":53}]}]}}'

# Or temporarily allow all DNS
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: <namespace>
spec:
  podSelector: {}
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: kube-system
    ports:
    - protocol: UDP
      port: 53
  - to:
    - podSelector: {}
EOF
```

### If CoreDNS Config Corrupted: Fix Configmap
```bash
# Restore default CoreDNS config
kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors
        health {
           lameduck 5s
        }
        ready
        kubernetes cluster.local in-addr.arpa ip6.arpa {
           pods insecure
           fallthrough in-addr.arpa ip6.arpa
        }
        prometheus :9153
        forward . /etc/resolv.conf {
           max_concurrent 1000
        }
        cache 30
        loop
        reload
        loadbalance
    }
EOF

# Restart CoreDNS
kubectl rollout restart deployment/coredns -n kube-system
```

### If Resource Constrained: Increase or Scale
```bash
# Scale up CoreDNS replicas
kubectl scale deployment coredns --replicas=5 -n kube-system

# Or increase resources
kubectl set resources deployment coredns -n kube-system \
  --limits=cpu=500m,memory=256Mi

# Redeploy
kubectl rollout restart deployment coredns -n kube-system
```

## Validation
```bash
# DNS should resolve quickly
kubectl run -it --rm dnstools --image=tutum/dnsutils --restart=Never -- \
  nslookup kubernetes.default

# Service discovery should work
kubectl run -it --rm dnstools --image=tutum/dnsutils --restart=Never -- \
  nslookup <service>.<namespace>.svc.cluster.local

# Application logs should show no DNS errors
kubectl logs <app-pod> -n <namespace> | grep -i "dns\|resolution" | wc -l
```

## Prevention
- Monitor CoreDNS pod restarts and CPU usage
- Alert on DNS query latency > 1 second
- Use multiple CoreDNS replicas for redundancy
- Configure pod disruption budgets for CoreDNS
- Test DNS resolution in staging before production
- Document DNS policies and troubleshooting
- Regular DNS performance monitoring

## Severity
**P1** - Blocks inter-service communication, service discovery fails completely.

## Escalation Matrix
| Status | Action |
|--------|--------|
| DNS works externally | Check cluster DNS config |
| CoreDNS pod down | Restart pod |
| High query latency | Scale/increase resources |
| Persistent failure | Page cluster administrator |
