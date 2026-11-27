# UniGlobe — Phase 4.7 Infrastructure Provisioning Authorization Checklist

**Date:** November 26, 2026  
**Audit Verdict:** Staging Manifests **`READY FOR INFRASTRUCTURE AUTHORIZATION`** | Live Pilot **`NO-GO`** (until Gates A–D + 12-Step E2E pass live)  
**Authorization Rule:** **Zero cloud services, VMs, buckets, or paid subscriptions have been created or purchased.** Explicit operator approval is required before provisioning any external resource below.

---

## 1. Exact External Resources Requiring Authorization

| Resource | Recommended Specification | Estimated Cost / Tier | Purpose & Isolation Boundary |
|---|---|---|---|
| **1. Linux Staging VM** | Ubuntu 24.04 LTS, **2 vCPU / 4 GB RAM min** (6–8 GB comfortable headroom), **30 GB encrypted disk**, static SSH/VPN-only ingress | Free trial / Always-Free ARM where eligible, or **`~$12–$30/mo`** (e.g., Hetzner/DO/EC2 `t4g.medium`) | Hosts `docker-compose.pilot.yml` (`postgres_pilot`, `clamav_pilot`, `api_pilot`, `web_pilot`). `<= 2 GB` RAM VMs will OOM-kill `clamd`. |
| **2. Clerk Staging Tenant** | Dedicated Clerk Development/Staging application (RS256 JWKS) | **$0/mo** (Free tier <= 10,000 MAU) | Gate A live JWT signing, rotation, login/logout for synthetic test accounts only. Never share production Clerk keys. |
| **3. Private Vault Bucket** | **Cloudflare R2** bucket `uniglobe-pilot-vault-private` *(or AWS S3 with Block Public Access ON + Object Ownership `BucketOwnerPreferred`)* | **$0/mo** (R2: <= 10 GB storage, 1M Class A ops, $0 egress; card on file may be needed) | Gate C live private SSE object storage, quarantined prefix isolation, pre-signed TTL expiry, public `403` block. |
| **4. Private Operator Tunnel** | SSH local port forward (`ssh -L 13000:127.0.0.1:13000 -L 18000:127.0.0.1:18000`) or WireGuard / Cloudflare Zero Trust Access | **$0/mo** (OpenSSH / Zero Trust <= 50 seats) | Enforces zero public exposure (`web_pilot` & `api_pilot` bind strictly to `127.0.0.1`). |
| **5. Antivirus Daemon (`clamav/clamav:stable`)** | Runs locally inside `clamav_pilot` on `pilot_internal` (`2048M` memory limit) | **$0/mo** (Open source) | Gate D live `zINSTREAM` TCP `3310` scanning & EICAR quarantine. *(Optional `$0/mo` staging Sentry free tier for error monitoring.)* |

**Maximum Estimated Recurring Spend (if using paid VM):** **`~$12–$30/month`** *(all SaaS/storage tiers are `$0/mo` within free limits).*

---

## 2. Explicit Operator Sign-Off Prerequisites (Before Provisioning)

- [ ] Approve provisioning an isolated Linux staging VM (`~$12–$30/mo` if no Always-Free eligible host is used) with host firewall blocking ports `3000`, `8000`, `5432`, `3310` from the public internet.
- [ ] Approve creating a dedicated non-production Clerk Staging tenant and injecting `CLERK_ISSUER`, `CLERK_JWKS_URL`, `CLERK_SECRET_KEY`, `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` into host-only `.env.pilot` (`chmod 0600`).
- [ ] Approve creating an isolated Cloudflare R2 (or S3 `BucketOwnerPreferred`) private staging bucket with bucket-scoped API keys (`PutObject`, `GetObject`, `DeleteObject` only) and Public Access disabled.
- [ ] Confirm **synthetic test accounts & dummy documents only** (`EICAR` test files and synthetic PDFs) will be used during Phase 4.8 live validation — **zero real student PII/transcripts**.

---

## 3. Provisioning, Validation & Rollback Sequence (Next Phase After Approval)

### A. Ordered Setup on Provisioned Ubuntu 24.04 Host
1. Lock VM inbound security group to SSH (`22`) from operator IP/VPN only. Install Docker Engine + Compose v2 plugin (`docker compose version`) and verify kernel `iptables` / `ip6tables` modules (`xt_owner`, `xt_conntrack`).
2. Clone repository privately (`git checkout main`), copy `infra/pilot/.env.pilot.example` to `infra/pilot/.env.pilot`, `chmod 600 infra/pilot/.env.pilot`, and populate all `REPLACE_WITH_*` secrets from password/secret manager.
3. Build images and bootstrap Docker networks (`br-uniglobe-pilot-egress` & `DOCKER-USER` chain MUST exist before attaching firewall):
   ```bash
   docker compose -f infra/pilot/docker-compose.pilot.yml build
   docker compose -f infra/pilot/docker-compose.pilot.yml up --no-start
   ```
4. Apply host kernel + Docker egress firewall (`127.0.0.11:53` Docker DNS permitted; RFC1918, `169.254.169.254`, IPv6 ULA/mapped blocked):
   ```bash
   export UNIGLOBE_WORKER_UID=10001
   export DOCKER_EGRESS_BRIDGE=br-uniglobe-pilot-egress
   sudo -E bash infra/firewall/egress-iptables.sh --apply
   sudo DOCKER_EGRESS_BRIDGE=br-uniglobe-pilot-egress bash infra/firewall/egress-iptables.sh --verify
   ```
   *(For reboot persistence on Ubuntu: install `iptables-persistent` / create a `systemd` oneshot unit with `After=docker.service` & `Requires=docker.service` executing `egress-iptables.sh --apply`.)*
5. Seed initial ClamAV signatures into `clamav_db_pilot` if `clamav_pilot` starts on `pilot_internal` without outbound access, then start stack:
   ```bash
   docker compose -f infra/pilot/docker-compose.pilot.yml up -d
   docker compose -f infra/pilot/docker-compose.pilot.yml ps
   ```
   Confirm `migrate_pilot` exited `0` (Alembic `a3c7e9f1b420`), `clamav_pilot` is `healthy`, `api_pilot` is `healthy`, and `web_pilot` is `healthy`.

### B. Live Gate & E2E Acceptance Verification
1. **Gate B Live SSRF Kernel Probe (from inside `api_pilot`):**
   ```bash
   docker exec uniglobe-pilot-api_pilot-1 python -c "import urllib.request; print(urllib.request.urlopen('http://169.254.169.254/latest/meta-data/', timeout=3).status)"
   ```
   Must fail immediately (`ConnectionRefusedError` / timeout) while `https://api.clerk.com` HTTPS check succeeds.
2. **Gates A, C, D Smoke Script:** Export two synthetic Clerk staging JWTs (`STAGING_STUDENT_A_JWT`, `STAGING_STUDENT_B_JWT`) and run:
   ```bash
   python3 infra/pilot/verify_staging_gates.py
   ```
3. **Bucket Public Access Block Check:** Confirm direct unauthenticated `curl -I` to the R2/S3 object key returns `403 AccessDenied` / `401`.
4. **Full 12-Step Staging E2E:** Register/login synthetic Student A & Student B via SSH-tunneled `http://127.0.0.1:13000`, verify profile creation, clean PDF SSE upload/presigned download, EICAR live `clamd` quarantine (`422` download/rescan block), cross-user `404` isolation, expired JWT `401`, and admin/verifier RBAC `403`.

### C. Rollback Commands (Database, Firewall, Stack)
- **Migration Rollback:** Take `pg_dump -Fc` before upgrade; if schema rollback is required:
  `docker compose -f infra/pilot/docker-compose.pilot.yml exec -T api_pilot alembic downgrade <previous_rev>` *(for Phase 4.3 `a3c7e9f1b420` -> `f1c9e4a2b870`)* or `pg_restore`.
- **Firewall Rollback:**
  ```bash
  sudo iptables -D DOCKER-USER -i br-uniglobe-pilot-egress -j UNIGLOBE_API_EGRESS 2>/dev/null || true
  sudo ip6tables -D DOCKER-USER -i br-uniglobe-pilot-egress -j UNIGLOBE_API_EGRESS_V6 2>/dev/null || true
  sudo iptables -D OUTPUT -m owner --uid-owner 10001 -j UNIGLOBE_API_EGRESS 2>/dev/null || true
  sudo ip6tables -D OUTPUT -m owner --uid-owner 10001 -j UNIGLOBE_API_EGRESS_V6 2>/dev/null || true
  sudo iptables -F UNIGLOBE_API_EGRESS && sudo iptables -X UNIGLOBE_API_EGRESS
  sudo ip6tables -F UNIGLOBE_API_EGRESS_V6 && sudo ip6tables -X UNIGLOBE_API_EGRESS_V6
  ```
- **Stack Teardown (preserving volumes) / Decommission (wiping synthetic staging data):**
  `docker compose -f infra/pilot/docker-compose.pilot.yml down` *(add `-v` only when intentionally destroying synthetic staging DB/AV volumes).*
