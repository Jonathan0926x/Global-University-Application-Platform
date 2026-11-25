# Production API Worker Outbound Firewall (Defense-in-Depth)

UniGlobe's link-health checker enforces application-layer SSRF protection via:
1. Structural URL validation (`validate_routing_url` — `https://`/`http://`, no localhost, no IP literals).
2. `follow_redirects=False` and `trust_env=False`.
3. `_PinnedPublicIPBackend` connection-time DNS validation + public IP pinning (mitigating DNS-rebinding TOCTOU).

As OS/infrastructure defense-in-depth for production API workers, apply **either** the Kubernetes `NetworkPolicy` or the host `iptables`/`ip6tables` ruleset in this directory:

## Blocked Egress Ranges
- **Cloud Instance Metadata:** `169.254.169.254/32` and `::ffff:169.254.169.254/128`
- **Link-Local:** `169.254.0.0/16`, `fe80::/10`, `::ffff:169.254.0.0/112`
- **Private Networks (RFC1918 & IPv6 ULA):** `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `fc00::/7`, and IPv4-mapped IPv6 equivalents
- **Loopback & CGNAT:** `127.0.0.0/8`, `::1/128`, `100.64.0.0/10`, `0.0.0.0/8`

## Commands
- Dry-run check: `bash infra/firewall/egress-iptables.sh --dry-run`
- Apply on Linux API host: `ALLOWED_DB_CIDR=10.20.0.10/32 ALLOWED_REDIS_CIDR=10.20.0.11/32 sudo bash infra/firewall/egress-iptables.sh --apply`
- Kubernetes deployment: `kubectl apply -f infra/firewall/k8s-api-worker-egress-networkpolicy.yaml`
