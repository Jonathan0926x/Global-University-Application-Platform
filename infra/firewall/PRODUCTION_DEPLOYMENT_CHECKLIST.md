# UniGlobe Production Outbound Worker Firewall — Deployment Checklist

**Defense-in-Depth Layer:** OS/Kernel Egress Filtering (`iptables`/`ip6tables` + Kubernetes `NetworkPolicy`)  
**Files:** [egress-iptables.sh](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/infra/firewall/egress-iptables.sh), [k8s-api-worker-egress-networkpolicy.yaml](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/infra/firewall/k8s-api-worker-egress-networkpolicy.yaml), [docker-compose.prod.yml](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/infra/firewall/docker-compose.prod.yml)

---

## 1. Environment Distinction: Local vs. Staging vs. Production

| Stage | Validation / Control Active | Status on Dev Workstation (macOS) |
|---|---|---|
| **Local Development & CI** | Application-layer SSRF checks (`validate_routing_url`, `_PinnedPublicIPBackend`, `follow_redirects=False`, `trust_env=False`) + `egress-iptables.sh --dry-run` syntax check | **Verified & Executed** |
| **Controlled Pilot / Staging** | Dedicated non-public Docker bridge (`internal_data` + `public_egress`) or Kubernetes namespace `uniglobe-pilot` with `NetworkPolicy` applied | **Pending Pilot Host Provisioning** |
| **Production** | Host kernel `iptables`/`ip6tables` attached to UID `uniglobe` (`UNIGLOBE_API_EGRESS` / `UNIGLOBE_API_EGRESS_V6`) AND Kubernetes `NetworkPolicy` active on worker pods | **Pending Production Deployment Authorization** |

> **Important:** Kernel `iptables` rules must be applied on Linux worker hosts with explicit operator authorization. Never execute destructive firewall rules unverified against a live host without a staged verification window.

---

## 2. Host Permissions & Prerequisites

1. **Linux Kernel Modules Required:** `ip_tables`, `ip6_tables`, `xt_owner` (`-m owner --uid-owner`), `xt_conntrack` (`-m conntrack --ctstate ESTABLISHED,RELATED`).
2. **Privilege Required:** `root` / `CAP_NET_ADMIN` to manipulate `OUTPUT`, `UNIGLOBE_API_EGRESS`, and `UNIGLOBE_API_EGRESS_V6`.
3. **Dedicated Service Account:** API worker processes MUST run under dedicated non-root UID/user (`UNIGLOBE_WORKER_UID=uniglobe` or UID `10001`). Database/Redis processes run under separate UIDs so worker UID egress drops cannot affect local admin SSH.
4. **Network Interfaces:**
   - Management/Ingress interface (`eth0` / internal load balancer): inbound HTTPS from reverse proxy only.
   - Internal bridge (`internal_data`): PostgreSQL (`5432`), Redis (`6379`), ClamAV (`3310`).
   - Egress bridge (`public_egress` / `br-uniglobe-egress`): outbound TCP `443` / `80` strictly excluding all private/reserved CIDRs.

---

## 3. Exact Firewall Rules & Allowed External Domains

### Blocked Egress CIDRs (IPv4 & IPv6)
- **Cloud Metadata:** `169.254.169.254/32`, `::ffff:169.254.169.254/128`
- **Link-Local:** `169.254.0.0/16`, `fe80::/10`, `::ffff:169.254.0.0/112`
- **RFC1918 Private:** `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` (+ `::ffff:*` mapped equivalents)
- **IPv6 Unique Local (ULA):** `fc00::/7` (includes AWS IPv6 IMDS `fd00:ec2::254`)
- **Loopback / Unspecified / CGNAT / Multicast:** `127.0.0.0/8`, `::1/128`, `100.64.0.0/10`, `0.0.0.0/8`, `224.0.0.0/4`, `240.0.0.0/4`, `ff00::/8`

### Allowed External Egress Destinations (TCP 443 Primary)
- **Identity Provider (JWKS & User Lookup):** `https://<instance>.clerk.accounts.dev`, `https://api.clerk.com`
- **Object Storage (Document Vault):** `https://<account>.r2.cloudflarestorage.com` or `https://s3.<region>.amazonaws.com`
- **Official Institutional & Scholarship Portals (Health Check Bot):** Verified `.edu`, `.ac.uk`, `.gov`, and catalog-registered sponsor/university portals.

---

## 4. Kubernetes NetworkPolicy Requirements

1. CNI plugin supporting `ipBlock.except` and `Egress` policies (e.g., **Calico**, **Cilium**, or **kube-router**; EKS default VPC CNI requires AWS Network Policy agent or Calico).
2. Pods running the FastAPI service MUST carry label `app: uniglobe-api-worker`.
3. `kube-dns` pods in `kube-system` must carry `k8s-app: kube-dns` so DNS lookup rule (UDP/TCP `53`) functions cleanly.
4. Apply policy:
   ```bash
   kubectl apply -f infra/firewall/k8s-api-worker-egress-networkpolicy.yaml
   ```

---

## 5. Step-by-Step Deployment & Verification Commands

1. **Dry-run Inspection:**
   ```bash
   bash infra/firewall/egress-iptables.sh --dry-run
   ```
2. **Apply on Authorized Linux Worker Host:**
   ```bash
   export ALLOWED_DB_CIDR="<db-private-ip>/32"
   export ALLOWED_REDIS_CIDR="<redis-private-ip>/32"
   export ALLOWED_DNS_CIDR="<dns-resolver-ip>/32"
   sudo -E bash infra/firewall/egress-iptables.sh --apply
   ```
3. **Rule Persistence (Debian/Ubuntu):**
   ```bash
   sudo netfilter-persistent save
   ```
4. **Live Connectivity & SSRF Block Verification (run as UID `uniglobe`):**
   ```bash
   sudo bash infra/firewall/egress-iptables.sh --verify
   # MUST FAIL (ECONNREFUSED / admin-prohibited):
   sudo -u uniglobe curl -m 3 http://169.254.169.254/latest/meta-data/ || echo "PASS: IMDS blocked"
   sudo -u uniglobe curl -m 3 http://127.0.0.1:8000/api/v1/health || echo "PASS: Loopback blocked"
   # MUST SUCCEED:
   sudo -u uniglobe curl -sI -m 5 https://api.clerk.com/v1/jwks || true
   ```

---

## 6. Emergency Rollback Procedure

```bash
sudo iptables -D OUTPUT -m owner --uid-owner uniglobe -j UNIGLOBE_API_EGRESS || true
sudo iptables -F UNIGLOBE_API_EGRESS || true
sudo iptables -X UNIGLOBE_API_EGRESS || true

sudo ip6tables -D OUTPUT -m owner --uid-owner uniglobe -j UNIGLOBE_API_EGRESS_V6 || true
sudo ip6tables -F UNIGLOBE_API_EGRESS_V6 || true
sudo ip6tables -X UNIGLOBE_API_EGRESS_V6 || true
```
*(In Kubernetes: `kubectl delete networkpolicy uniglobe-api-worker-egress -n uniglobe-prod`.)*
