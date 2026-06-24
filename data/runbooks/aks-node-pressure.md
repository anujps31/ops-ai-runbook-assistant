# AKS Node Pressure Runbook

## Problem
Azure Kubernetes Service (AKS) nodes experience resource pressure conditions (memory, disk, or PID pressure), causing Kubernetes to evict pods and potentially making nodes unavailable.

## Symptoms
1. Node conditions show MemoryPressure or DiskPressure: True
2. Pods evicted from node with "Evicted" status
3. Node status shows "NotReady"
4. Resource pressure metrics elevated
5. Kernel messages: "Out of memory" or "No space left on device"
6. Node capacity reduced in kubectl top
7. PID pressure (too many processes)
8. Node kubelet reporting resource pressure
9. Pod disruptions increasing
10. Azure agent unable to update

## Possible Root Causes
1. **Memory pressure**: Pods using more memory than allocated
2. **Disk pressure**: Logs or container images filling disk
3. **PID pressure**: Too many processes created
4. **Node misconfiguration**: Limits too low for workload
5. **Resource leak**: Pod consuming memory indefinitely
6. **Log accumulation**: Logs not rotated, filling disk
7. **Docker/Containerd storage**: Image layers consuming space
8. **Kubelet eviction threshold**: Too aggressive eviction
9. **Cluster node pool sizing**: Wrong machine type
10. **Azure Blob storage**: Persistent volumes mounting incorrectly

## Investigation Steps

### Step 1: Check Node Conditions
```bash
# Get node status
kubectl get nodes

# Check specific node
kubectl describe node <node-name>

# Look for condition status:
# MemoryPressure = True or DiskPressure = True

# Get detailed condition info
kubectl get node <node-name> -o jsonpath='{.status.conditions}'

# Check when condition appeared
kubectl get events --field-selector involvedObject.name=<node-name> | grep Pressure
```

### Step 2: Check Node Resource Usage
```bash
# Get node metrics
kubectl top node <node-name>

# Get allocatable resources
kubectl get node <node-name> -o jsonpath='{.status.allocatable}'

# Get requested vs allocatable
kubectl get pods --all-namespaces -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\t"}{.spec.containers[0].resources.requests.memory}{"\n"}{end}' | \
  awk '{sum+=$3} END {print "Total memory requested: " sum}'

# Get actual usage
kubectl top node <node-name> | grep -oP '\d+Mi' | tail -1
```

### Step 3: Check Evicted Pods
```bash
# Get evicted pods
kubectl get pods --all-namespaces | grep Evicted

# Get eviction reason
kubectl describe pod <evicted-pod> -n <namespace> | grep -A 5 "Reason:"

# Check eviction history
kubectl get events -n <namespace> --field-selector involvedObject.kind=Pod | grep Evicted

# Get pods on specific node (before eviction)
kubectl get pods --all-namespaces -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\t"}{.spec.nodeName}{"\n"}{end}' | grep <node-name>
```

### Step 4: SSH to Node and Check Disk
```bash
# SSH to Azure node
ssh -i ~/.ssh/id_rsa azureuser@<node-ip>

# Check disk usage
df -h

# Find large directories
du -sh /* | sort -rh | head -10

# Check specific kubelet directory
du -sh /var/lib/kubelet/*

# Check container logs
du -sh /var/lib/kubelet/pods/*/volume-subpaths/

# Check docker/containerd
du -sh /var/lib/docker
du -sh /var/lib/containerd

# Check if any filesystem at 100%
df -h | grep 100%
```

### Step 5: Check Kubelet Eviction Policy
```bash
# SSH to node
ssh azureuser@<node-ip>

# Check kubelet service config
cat /etc/systemd/system/kubelet.service.d/10-kubeadm.conf | grep -i "evict"

# Or check running kubelet
ps aux | grep kubelet | grep -o "\-\-eviction.*"

# Check eviction thresholds (default settings)
# --eviction-hard=memory.available<100Mi,nodefs.available<10%,nodefs.inodesFree<5%

# If thresholds too aggressive, increase them
# Edit: /etc/kubernetes/kubelet.config
# evictionHard:
#   memory.available: "150Mi"
#   nodefs.available: "15%"

# Restart kubelet
sudo systemctl restart kubelet
```

### Step 6: Check Running Pods for Issues
```bash
# SSH to node
ssh azureuser@<node-ip>

# Get all processes
ps aux | sort -k4 -rn | head -20

# Check for runaway processes
# If single process using >50% memory = leak or issue

# Check process count (PID pressure)
ps aux | wc -l

# If > 5000 processes, PID pressure likely

# Get most memory-intensive process
ps aux --sort=-%mem | head -10
```

### Step 7: Check Container Storage
```bash
# SSH to node
ssh azureuser@<node-ip>

# List docker/containerd images
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"

# Check for unused layers
docker system df

# List containers
docker ps -a

# Check container logs size
ls -lh /var/lib/docker/containers/*/

# Find largest log files
find /var/lib/docker/containers -name "*.log" -exec du -h {} \; | sort -rh | head -10
```

### Step 8: Check Azure VM Metrics
```bash
# From Azure CLI:
az monitor metrics list \
  --resource /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.Compute/virtualMachines/<vm-name> \
  --metric "Percentage CPU" \
  --start-time 2024-01-01T00:00:00Z

# Or check available memory from Azure
az vm get-instance-view \
  --resource-group <rg> \
  --name <vm-name> \
  --query "hardwareProfile"

# Check if VM right-sized for workload
# If small node type (B1s, B2s), likely resource constrained
```

### Step 9: Check Kubelet Logs
```bash
# SSH to node
ssh azureuser@<node-ip>

# Check kubelet service logs
journalctl -u kubelet -n 100 | tail -50

# Look for eviction messages
journalctl -u kubelet | grep -i "evict"

# Look for memory/disk pressure messages
journalctl -u kubelet | grep -i "pressure\|disk\|memory"

# Check system logs
dmesg | tail -50

# Look for OOM killer
dmesg | grep -i "out of memory"
```

### Step 10: Check Azure Resources
```bash
# Check AKS cluster node pool configuration
az aks nodepool list --resource-group <rg> --cluster-name <cluster> -o table

# Get specific node pool details
az aks nodepool show \
  --resource-group <rg> \
  --cluster-name <cluster> \
  --name <nodepool-name> \
  --query "vmSize"

# Check if node pool has enough capacity
# Example: Standard_B2s (2 vCPU, 4GB RAM) vs Standard_D4s_v3 (4 vCPU, 16GB RAM)
```

## Resolution Steps

### If Memory Pressure: Reduce Pod Memory or Scale
```bash
# Option 1: Reduce memory requests of pods
kubectl set resources deployment/<name> -n <namespace> \
  --requests=memory=512Mi

# Option 2: Delete non-essential pods temporarily
kubectl delete pod <pod-name> -n <namespace>

# Option 3: Add more nodes to node pool
az aks nodepool scale \
  --resource-group <rg> \
  --cluster-name <cluster> \
  --name <nodepool-name> \
  --node-count 5  # Increase from current count

# Option 4: Use node pool with larger VM
az aks nodepool add \
  --resource-group <rg> \
  --cluster-name <cluster> \
  --name large-pool \
  --vm-set-type VirtualMachineScaleSets \
  --node-count 3 \
  --node-vm-size Standard_D4s_v3
```

### If Disk Pressure: Clean Disk Space
```bash
# SSH to node
ssh azureuser@<node-ip>

# Clean docker images (caution!)
docker image prune -a --force

# Clean docker volumes
docker volume prune --force

# Remove old container logs
find /var/lib/kubelet/pods -name "*.log" -mtime +7 -delete

# Compress old kubelet logs
gzip /var/log/kubelet/*.log

# Clean container runtime storage
containerd cleanup

# Restart kubelet
sudo systemctl restart kubelet

# Verify freed space
df -h
```

### If PID Pressure: Investigate Process Leak
```bash
# SSH to node
ssh azureuser@<node-ip>

# Find process spawning many PIDs
ps aux | wc -l

# Identify which user/process
ps aux | awk '{print $1}' | sort | uniq -c | sort -rn | head -10

# Kill if necessary (caution!)
killall -9 <process-name>

# Or increase PID limit (global)
echo "vm.pid_max = 4194304" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Restart kubelet
sudo systemctl restart kubelet
```

### If Kubelet Evicting Too Aggressively: Adjust Thresholds
```bash
# SSH to node
ssh azureuser@<node-ip>

# Edit kubelet config
sudo nano /etc/kubernetes/kubelet.config

# Adjust eviction thresholds:
evictionHard:
  memory.available: "200Mi"      # From 100Mi
  nodefs.available: "15%"        # From 10%
  nodefs.inodesFree: "10%"       # From 5%

# Save and restart
sudo systemctl restart kubelet

# Verify changes applied
ps aux | grep kubelet | grep eviction
```

### If Node Undersized: Upgrade VM
```bash
# Drain node gracefully
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data

# SSH to node and update VM size (if possible)
# For VMSS: Update scale set
az vmss update \
  --resource-group <rg> \
  --name <vmss-name> \
  --sku Standard_D4s_v3

# Or add new node pool and migrate workload
az aks nodepool add \
  --resource-group <rg> \
  --cluster-name <cluster> \
  --name upgraded-pool \
  --vm-set-type VirtualMachineScaleSets \
  --node-vm-size Standard_D4s_v3

# Update pod affinity to new pool
kubectl patch pod <pod> -n <namespace> -p \
  '{"spec":{"nodeSelector":{"agentpool":"upgraded-pool"}}}'

# Remove old node
kubectl delete node <old-node-name>
```

## Validation
```bash
# Node conditions should be clear
kubectl describe node <node-name> | grep Pressure

# Should show: MemoryPressure = False, DiskPressure = False

# Node should be Ready
kubectl get nodes | grep <node-name>

# Disk usage should be healthy
ssh azureuser@<node-ip>
df -h | grep "100%" | wc -l
# Should be 0

# No pods Evicted
kubectl get pods --all-namespaces | grep Evicted | wc -l
# Should be 0
```

## Prevention
- Monitor node resource usage continuously
- Set alerts for resource pressure conditions
- Right-size node pool VMs for workload
- Implement PodDisruptionBudgets
- Use cluster autoscaling with appropriate node types
- Implement resource quotas per namespace
- Clean up old pods/containers regularly
- Configure log rotation with appropriate retention
- Test node failure scenarios
- Document expected per-pod resource usage

## Severity
**P1** - Nodes unavailable, pods evicted, service degraded.

## Escalation Matrix
| Condition | Action |
|-----------|--------|
| MemoryPressure | Scale pods or add nodes |
| DiskPressure | Clean disk space |
| PIDPressure | Investigate process leaks |
| Multiple nodes | Escalate to infrastructure |
| Persistent | Page on-call manager |
