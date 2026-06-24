# SSL Certificate Expired Runbook

## Problem
SSL/TLS certificates used by Kubernetes ingress, services, or applications have expired, causing SSL handshake failures and blocking encrypted traffic.

## Symptoms
1. HTTPS requests fail with "certificate expired" error
2. Browser shows "ERR_CERT_DATE_INVALID"
3. curl shows "certificate verify failed"
4. Application logs show "ssl_error_rx_record_too_long"
5. Ingress controller logs show certificate issues
6. Service-to-service communication fails (mTLS)
7. Webhook calls rejected (cert expired)
8. Specific domain/service inaccessible over HTTPS
9. Certificate warning appeared days/weeks ago (ignored)
10. Multiple services affected simultaneously (batch expiration)

## Impact
- **Availability**: HTTPS traffic blocked completely
- **Security**: Cannot communicate over encrypted channels
- **Integration**: External services cannot call APIs
- **Webhooks**: CI/CD, payments, events fail
- **Client trust**: Errors undermine confidence

## Possible Root Causes
1. **No auto-renewal**: Manual renewal process not executed
2. **Renewal failure**: cert-manager or renewal automation failed
3. **Forgotten manual cert**: Certificate created manually, renewal oversight
4. **Webhook cert**: Internal CA certificate expired
5. **Batch expiration**: Multiple certs purchased same time
6. **Old certificate**: Never replaced after expiration
7. **Clock skew**: Node time ahead of actual time (server clock fast)
8. **Certificate reissue needed**: Old cert authority deprecated
9. **Domain validation failure**: Domain verification for renewal failed
10. **Disk full**: cert-manager cannot write new certificate

## Investigation Steps

### Step 1: Identify Expired Certificate
```bash
# Check ingress certificate expiration
kubectl get ingress -A -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\t"}{.spec.tls[0].secretName}{"\n"}{end}'

# Get certificate expiration from secret
kubectl get secret <cert-secret> -n <namespace> -o jsonpath='{.data.tls\.crt}' | base64 -d | \
  openssl x509 -text -noout | grep -A 2 "Not After"

# Check all certs in namespace
for secret in $(kubectl get secrets -n <namespace> -o name | grep tls); do
  echo "=== $secret ==="
  kubectl get secret $secret -n <namespace> -o jsonpath='{.data.tls\.crt}' | base64 -d | \
    openssl x509 -text -noout 2>/dev/null | grep -A 1 "Not After" || echo "Not a cert"
done

# Check certificate validity
echo | openssl s_client -servername <domain> -connect <domain>:443 2>/dev/null | \
  openssl x509 -text -noout | grep -A 1 "Not After"
```

### Step 2: Check cert-manager Status
```bash
# Check if cert-manager running
kubectl get pods -n cert-manager

# Get certificate resources
kubectl get certificate -A

# Check certificate status
kubectl describe certificate <cert-name> -n <namespace>

# Check for renewal issues
kubectl describe certificate <cert-name> -n <namespace> | grep -i "renewal\|error"

# Check certificaterequest status
kubectl get certificaterequest -n <namespace>

# Check ClusterIssuer/Issuer status
kubectl describe clusterissuer <issuer-name>
kubectl describe issuer <issuer-name> -n <namespace>
```

### Step 3: Verify Certificate Renewal Configuration
```bash
# Check certificate renewal settings
kubectl get certificate <cert-name> -n <namespace> -o yaml | grep -i "renew\|duration"

# Check issuer configuration
kubectl get issuer <issuer-name> -n <namespace> -o yaml

# Look for renewal times (default: 30 days before expiry)
# Certificate created_at + validity_period = expiry
# Renewal attempts at: expiry - 30 days

# Check if there's a pattern (all certs expire same date)
kubectl get certificate -A -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\t"}{.status.renewalTime}{"\n"}{end}'
```

### Step 4: Check System Time
```bash
# Verify system time is correct (clock skew can cause issues)
date && kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.conditions[] | select(.type=="Ready") | .lastHeartbeatTime}{"\n"}{end}'

# Check NTP sync on nodes
kubectl exec <pod> -n <namespace> -- date
ssh <node-ip> date

# If clocks don't match, sync time:
sudo timedatectl set-ntp true
sudo systemctl restart chronyd
```

### Step 5: Check Certificate Secret Exists
```bash
# Verify secret exists with certificate data
kubectl get secret <cert-secret> -n <namespace>
kubectl get secret <cert-secret> -n <namespace> -o yaml

# Check if tls.crt and tls.key present
kubectl get secret <cert-secret> -n <namespace> -o jsonpath='{.data}' | jq 'keys'

# Check secret size (empty = problem)
kubectl get secret <cert-secret> -n <namespace> -o jsonpath='{.data.tls\.crt}' | wc -c
```

### Step 6: Check Certificate Events and Logs
```bash
# Get recent events related to certificate
kubectl get events -n <namespace> --field-selector involvedObject.name=<cert-name>

# Check cert-manager logs for renewal attempts
kubectl logs -n cert-manager -l app=cert-manager -n cert-manager | grep <cert-name> | tail -50

# Check webhook logs
kubectl logs -n cert-manager -l app=webhook | grep -i "error\|fail" | tail -30

# Check ingress controller logs
kubectl logs -n ingress-nginx -l app=ingress-nginx | grep -i "cert\|tls" | tail -30
```

### Step 7: Verify Ingress Tls Configuration
```bash
# Check ingress TLS spec
kubectl get ingress <ingress-name> -n <namespace> -o yaml | grep -A 10 "tls:"

# Verify secretName matches actual secret
kubectl get secret <secret-name> -n <namespace>

# Check if cert secret is in correct namespace
# Secret must be in same namespace as ingress

# Check ingress annotation for cert-manager
kubectl get ingress <ingress-name> -n <namespace> -o yaml | grep -i "cert-manager"
```

### Step 8: Check External Certificate Provider
```bash
# If using external CA (not cert-manager):

# For Let's Encrypt: check account status
# curl https://acme-v02.api.letsencrypt.org/

# For AWS Certificate Manager:
aws acm list-certificates
aws acm describe-certificate --certificate-arn <arn>

# For Azure Key Vault:
az keyvault certificate list --vault-name <vault>

# For Google Cloud:
gcloud compute ssl-certificates list
```

### Step 9: Check Rate Limiting and API Issues
```bash
# Check if rate limited (Let's Encrypt has limits)
# If many cert renewals: 50 certs per domain per week

# Check DNS for CAA records (certificate authority authorization)
dig CAA <domain>

# Verify domain validation method (DNS/HTTP)
kubectl describe certificate <cert-name> -n <namespace> | grep -i "validation"

# Check HTTP/DNS challenge pods
kubectl get pods -n cert-manager | grep -i "challenge"
```

### Step 10: Test Certificate After Fix
```bash
# Test HTTPS connectivity
curl -I https://<domain>

# Test with verbose output
curl -v https://<domain> 2>&1 | grep -i "certificate\|expire"

# Check certificate in browser
# Open https://<domain> in browser, click padlock icon

# Verify certificate details
openssl s_client -connect <domain>:443 -showcerts 2>/dev/null | \
  openssl x509 -text -noout | grep -E "Subject|Not Before|Not After"
```

## Resolution Steps

### If Certificate Expired: Immediate Action
```bash
# Option 1: Use cert-manager to reissue (fastest)
kubectl delete certificaterequest --all -n <namespace>
kubectl delete certificate <cert-name> -n <namespace>
kubectl apply -f <cert-yaml>  # Re-apply certificate definition

# Option 2: Manually issue Let's Encrypt certificate
kubectl create secret tls <secret-name> \
  --cert=<new-cert>.crt \
  --key=<new-cert>.key \
  -n <namespace>

# Update ingress to reference new secret
kubectl patch ingress <ingress-name> -n <namespace> -p \
  '{"spec":{"tls":[{"hosts":["<domain>"],"secretName":"<new-secret>"}]}}'
```

### If cert-manager Not Working: Troubleshoot
```bash
# Restart cert-manager
kubectl rollout restart deployment/cert-manager -n cert-manager
kubectl rollout restart deployment/cert-manager-webhook -n cert-manager

# Check for errors in logs
kubectl logs -n cert-manager -l app=cert-manager | grep -i "error"

# Verify ClusterIssuer connectivity
kubectl describe clusterissuer <issuer> | grep -i "status\|reason\|message"

# Fix ACME account issue (if present)
kubectl patch clusterissuer <issuer> --type json -p='[{"op": "replace", "path": "/spec/acme/email", "value":"new-email@example.com"}]'
```

### If Manual Certificate Needed Temporarily
```bash
# Generate self-signed cert for emergency use
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Create secret from cert
kubectl create secret tls emergency-cert \
  --cert=cert.pem \
  --key=key.pem \
  -n <namespace>

# Update ingress
kubectl patch ingress <ingress-name> -n <namespace> -p \
  '{"spec":{"tls":[{"hosts":["<domain>"],"secretName":"emergency-cert"}]}}'

# Plan permanent solution in parallel
```

### If Clock Skew: Fix Time
```bash
# SSH to each node and sync time
ssh <node-ip>
sudo timedatectl set-ntp true
sudo date -s "$(curl -s https://www.google.com | grep -oP '(?<=Date: ).*?(?=GMT)')"

# Verify sync
date

# Restart cert-manager pods
kubectl rollout restart deployment/cert-manager -n cert-manager
```

## Validation
```bash
# Certificate should no longer be expired
openssl s_client -connect <domain>:443 2>/dev/null | \
  openssl x509 -text -noout | grep "Not After"

# HTTPS should work
curl -I https://<domain>  # Should return HTTP/2 200

# Ingress should show certificate
kubectl describe ingress <ingress-name> -n <namespace> | grep -i "tls"

# No certificate errors in logs
kubectl logs -n ingress-nginx | grep -i "cert.*expire"
```

## Prevention
- Set calendar reminders for certificate renewals (60 days before)
- Enable cert-manager with auto-renewal (30 days before expiry)
- Monitor certificate expiration dates continuously
- Use monitoring alerts for certs expiring within 30 days
- Regular audit of all certificates in cluster
- Document certificate sources and renewal procedures
- Test renewal process in staging before production
- Implement automated certificate rotation
- Use long-lived certificates (1+ years) with renewal

## Severity
**P1** - Blocks HTTPS access, can cause complete service unavailability for users.

## Escalation Matrix
| When | Action |
|------|--------|
| > 7 days before expiry | Start renewal process |
| 7-1 days | Monitor renewal completion |
| < 1 day | Emergency renewal or temporary cert |
| Expired | Page on-call, immediate action |
