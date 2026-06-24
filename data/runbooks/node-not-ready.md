# Kubernetes Node Not Ready Runbook

## Problem
A Kubernetes worker node enters `NotReady` state, preventing pod scheduling and causing existing workloads on that node to become unschedulable. The node continues running but Kubernetes treats it as unavailable.

## Symptoms
1. Node status shows `NotReady` in kubectl get nodes
2. Conditions show `Ready=False` with reason `KubeletNotReady`
3. Pods on affected node evicted to other nodes
4. New pod scheduling avoids the node
5. Node CPU/Memory metrics unavailable in kubectl top
6. Pod events show "node has conditions incompatible for pod scheduling"
7. Kubelet process running but not responding to API
8. No kubelet logs available for recent activity
9. Network connectivity to node appears functional but API unresponsive
10. Other nodes operating normally, only specific node affected

## Impact
- **Capacity**: Cluster loses node capacity, may cause pod eviction
- **Workload migration**: Pods forced to reschedule to other nodes
- **Ripple effects**: Other nodes become overloaded, may trigger cascading failures
- **Drain delay**: Workloads not gracefully drained, immediate termination
- **SLA**: If pods can't reschedule, service unavailable

## Possible Root Causes
1. **Kubelet crashed**: Process stopped responding or died
2. **Disk pressure**: Node disk full, kubelet unable to create container runtime sockets
3. **Memory pressure**: Node out of memory, kubelet becoming unresponsive
4. **Network connectivity**: Node isolated from cluster network or API server
5. **API server unreachable**: Node cannot contact API server for checkin
6. **Container runtime failure**: Docker/containerd daemon crashed or hung
7. **Kernel panic**: Node kernel unstable, reboot required
8. **Disk I/O errors**: Disk failing, reads/writes timing out
9. **Too many open files**: inode exhaustion or file descriptor limits
10. **Time synchronization**: Node clock out of sync with cluster

## Investigation Steps

### Step 1: Check Node Status Details
```bash
# Get detailed node status
kubectl describe node <node-name>

# Check specific node conditions
kubectl get node <node-name> -o jsonpath='{.status.conditions}' | jq .

# Extract reason and message
kubectl get node <node-name> -o jsonpath='{.status.conditions[] | select(.type=="Ready") | {status: .status, reason: .reason, message: .message}}'

# Check when status changed
kubectl get events --field-selector involvedObject.name=<node-name> | tail -20
```

### Step 2: SSH to Node and Check Kubelet Status
```bash
# Connect to node via SSH
ssh <node-ip>

# Check kubelet service status
systemctl status kubelet

# Get kubelet process status
ps aux | grep kubelet

# Check kubelet is actually running
pidof kubelet

# Get kubelet service logs (recent)
journalctl -u kubelet -n 50
journalctl -u kubelet -n 100 | grep -i "error\|fail"
```

### Step 3: Check Disk Space
```bash
# SSH to node
ssh <node-ip>

# Check overall disk usage
df -h

# Check specific filesystem usage
df -h /var/lib/docker
df -h /var/lib/kubelet
df -h /var/log

# Check for specific large files
du -sh /* | sort -rh | head -10

# Check inode usage
df -i /

# Identify space-consuming directories
du -sh /var/lib/kubelet/* | sort -rh

# Check docker image storage
docker system df

# Look for stale pod storage
ls -lh /var/lib/kubelet/pods/ | head -20
```

### Step 4: Check Container Runtime
```bash
# SSH to node
ssh <node-ip>

# Check docker status
systemctl status docker
docker ps | head -10
docker images | wc -l

# Or check containerd status
systemctl status containerd
crictl ps | head -10

# Check container runtime logs
journalctl -u docker -n 50
journalctl -u containerd -n 50

# Try pulling test image
docker pull nginx:latest

# Check for container runtime hung
crictl info || docker info
```

### Step 5: Check Network Connectivity
```bash
# From control plane or bastion, test network to node
ping -c 5 <node-ip>

# Test API port connectivity
telnet <node-ip> 10250 (kubelet)
telnet <node-ip> 10255 (read-only kubelet)

# From node, verify can reach API server
ssh <node-ip>
curl -k https://<api-server-ip>:6443/version

# Check firewall rules
iptables -L | grep <api-server-ip>
ufw status | grep ALLOW
```

### Step 6: Check Node Memory and CPU
```bash
# SSH to node
ssh <node-ip>

# Check memory
free -h
vmstat 1 5

# Check CPU
top -b -n 1 | head -20

# Check for memory pressure
cat /proc/meminfo | grep -E "MemAvailable|MemFree"

# Check swap usage
swapon -s

# Check load average
uptime
```

### Step 7: Check Kubelet Configuration and Logs
```bash
# SSH to node
ssh <node-ip>

# Check kubelet config
cat /etc/systemd/system/kubelet.service.d/10-kubeadm.conf

# Tail kubelet logs in real-time
journalctl -u kubelet -f

# Check kubelet certificate expiration
cat /var/lib/kubelet/pki/kubelet.crt | openssl x509 -text -noout | grep -A 2 "Not After"

# Verify kubelet can communicate with API server
kubelet --version
systemctl restart kubelet
journalctl -u kubelet -n 20
```

### Step 8: Check API Server Connectivity
```bash
# From node, test API server connectivity
ssh <node-ip>

# Find API server address
grep "server:" /etc/kubernetes/kubelet.conf | head -1

# Test connectivity
curl -k --cert /var/lib/kubelet/pki/kubelet-client-current.pem \
     --key /var/lib/kubelet/pki/kubelet-client-current.pem \
     https://<api-server>:6443/version

# Check API server firewall rules
iptables -L -n | grep 6443
```

### Step 9: Examine System Logs and Kernel
```bash
# SSH to node
ssh <node-ip>

# Check for kernel panic
dmesg | tail -50

# Look for memory errors
dmesg | grep -i "oom\|memory\|error"

# Check for disk errors
dmesg | grep -i "i/o error\|disk fail"

# Check system time sync
timedatectl
chronyc sources

# Check time difference from control plane
date && ssh <control-plane-node> date
```

### Step 10: Verify Node Ready Status After Changes
```bash
# From control plane, watch node status
kubectl get nodes -w

# Check specific node conditions
kubectl get node <node-name> -o jsonpath='{.status.conditions}' | jq .

# Get pod status on node after recovery
kubectl get pods --all-namespaces --field-selector spec.nodeName=<node-name>
```

## Resolution Steps

### If Kubelet Stopped: Restart It
```bash
# SSH to node
ssh <node-ip>

# Restart kubelet service
sudo systemctl restart kubelet

# Monitor restart
sudo systemctl status kubelet
sudo journalctl -u kubelet -f

# Check node status from control plane
kubectl get nodes --watch

# Should see NotReady -> Ready transition
```

### If Disk Full: Clean Up
```bash
# SSH to node
ssh <node-ip>

# Clean docker images
docker image prune -a --force

# Clean unused volumes
docker volume prune --force

# Remove old pod logs
journalctl --vacuum=500M

# Clean kubelet pod logs
rm -rf /var/lib/kubelet/pods/*/volume-subpaths

# Clean container runtime storage
crictl rmi --prune || docker system prune --volumes -f

# Restart kubelet after cleanup
sudo systemctl restart kubelet
```

### If Network Issue: Verify Connectivity
```bash
# SSH to node
ssh <node-ip>

# Check network interface status
ip link show

# Check routing
ip route show

# Restart networking
sudo systemctl restart networking

# For cloud environments, check security groups/network policies
# AWS: Check security group rules
# Azure: Check NSG rules
# GCP: Check firewall rules
```

### If API Server Unreachable: Update Config
```bash
# SSH to node
ssh <node-ip>

# Verify API server address in kubelet config
grep "server:" /etc/kubernetes/kubelet.conf

# If incorrect, update:
sed -i 's|https://old-api:6443|https://new-api:6443|' /etc/kubernetes/kubelet.conf

# Restart kubelet
sudo systemctl restart kubelet
```

### If Time Out of Sync: Sync Clock
```bash
# SSH to node
ssh <node-ip>

# Check current time
date

# Sync time using NTP
sudo timedatectl set-ntp true

# Or manually set time
sudo date -s "$(curl -s https://www.google.com | grep -oP '(?<=Date: ).*?(?=GMT)')"

# Verify sync
date && date -u

# Restart kubelet after time correction
sudo systemctl restart kubelet
```

## Validation
```bash
# Node should reach Ready state
kubectl get nodes --watch

# Check all conditions are True
kubectl get node <node-name> -o jsonpath='{.status.conditions}' | jq .

# Pods should be scheduled to node
kubectl get pods --all-namespaces --field-selector spec.nodeName=<node-name>

# Metrics should be available
kubectl top node <node-name>

# No recent events about node issues
kubectl get events --field-selector involvedObject.name=<node-name> | tail -5
```

## Prevention
- Monitor node disk usage and set alerts at 80% threshold
- Implement automated disk cleanup policies
- Monitor kubelet process and restart if crashed
- Implement NTP time synchronization on all nodes
- Set up network connectivity monitoring
- Configure kubelet certificate rotation before expiration
- Use health check endpoints to detect node issues early
- Implement node auto-repair mechanisms
- Regular node OS and kernel updates in maintenance windows
- Monitor system load and memory on nodes

## Severity
**P1** - Reduces cluster capacity and may cause service unavailability if pods can't reschedule.

## Escalation Matrix
| Duration | Action |
|----------|--------|
| < 5 min | SSH to node, check kubelet status |
| 5-15 min | Restart kubelet or reboot node |
| 15-30 min | Investigate underlying infrastructure |
| 30-60 min | Page infrastructure team, consider node termination |
| > 60 min | Escalate to cloud provider if cloud-based |
