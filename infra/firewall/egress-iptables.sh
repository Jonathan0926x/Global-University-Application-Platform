#!/usr/bin/env bash
# UniGlobe Production API Worker Outbound Firewall (Defense-in-Depth vs SSRF / DNS Rebinding)
# Explicitly blocks RFC1918 private ranges, loopback, CGNAT, link-local, IPv6 private/mapped ranges,
# and cloud instance metadata (169.254.169.254) for API worker egress traffic.
#
# Usage:
#   ./egress-iptables.sh --dry-run   # Print exact iptables/ip6tables rules without modifying host
#   sudo ./egress-iptables.sh --apply
#   sudo ./egress-iptables.sh --verify

set -euo pipefail

MODE="${1:---dry-run}"
CHAIN_V4="UNIGLOBE_API_EGRESS"
CHAIN_V6="UNIGLOBE_API_EGRESS_V6"
WORKER_UID="${UNIGLOBE_WORKER_UID:-uniglobe}"
DOCKER_EGRESS_BRIDGE="${DOCKER_EGRESS_BRIDGE:-}"
ALLOWED_DB_CIDR="${ALLOWED_DB_CIDR:-}"
ALLOWED_REDIS_CIDR="${ALLOWED_REDIS_CIDR:-}"
ALLOWED_DNS_CIDR="${ALLOWED_DNS_CIDR:-}"

BLOCKED_IPV4_CIDRS=(
  "169.254.169.254/32"  # Cloud metadata endpoint (AWS/GCP/Azure/Oracle)
  "169.254.0.0/16"      # Link-local
  "10.0.0.0/8"          # RFC1918 private Class A
  "172.16.0.0/12"       # RFC1918 private Class B (incl. Docker default bridges)
  "192.168.0.0/16"      # RFC1918 private Class C
  "127.0.0.0/8"         # IPv4 loopback
  "100.64.0.0/10"       # Carrier-grade NAT (RFC6598)
  "0.0.0.0/8"           # Unspecified / current network
  "224.0.0.0/4"         # Multicast
  "240.0.0.0/4"         # Reserved
)

BLOCKED_IPV6_CIDRS=(
  "::1/128"                     # IPv6 loopback
  "fe80::/10"                   # IPv6 link-local
  "fc00::/7"                    # IPv6 unique local (ULA)
  "ff00::/8"                    # IPv6 multicast
  "::ffff:169.254.169.254/128"  # IPv4-mapped metadata
  "::ffff:169.254.0.0/112"      # IPv4-mapped link-local
  "::ffff:10.0.0.0/104"         # IPv4-mapped RFC1918 Class A
  "::ffff:172.16.0.0/108"       # IPv4-mapped RFC1918 Class B
  "::ffff:192.168.0.0/112"      # IPv4-mapped RFC1918 Class C
  "::ffff:127.0.0.0/104"        # IPv4-mapped loopback
  "::ffff:100.64.0.0/106"       # IPv4-mapped CGNAT
)

run_cmd() {
  if [[ "$MODE" == "--dry-run" ]]; then
    printf '%s\n' "$*"
  else
    "$@"
  fi
}

preflight_live() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "ERROR: $MODE must run as root (use sudo -E)." >&2
    exit 1
  fi
  for bin in iptables ip6tables; do
    if ! command -v "$bin" >/dev/null 2>&1; then
      echo "ERROR: Required firewall binary '$bin' not found on host." >&2
      exit 1
    fi
  done
  if [[ "$MODE" == "--apply" && -n "$DOCKER_EGRESS_BRIDGE" ]]; then
    if ! iptables -L DOCKER-USER -n >/dev/null 2>&1; then
      echo "ERROR: DOCKER-USER iptables chain not found. Start Docker daemon / create network first before --apply with DOCKER_EGRESS_BRIDGE=$DOCKER_EGRESS_BRIDGE." >&2
      exit 1
    fi
  fi
}

apply_rules() {
  if [[ "$MODE" != "--dry-run" ]]; then
    preflight_live
  fi

  # IPv4 chain setup
  run_cmd iptables -N "$CHAIN_V4" 2>/dev/null || true
  run_cmd iptables -F "$CHAIN_V4"
  run_cmd iptables -A "$CHAIN_V4" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

  if [[ -n "$ALLOWED_DB_CIDR" ]]; then
    run_cmd iptables -A "$CHAIN_V4" -p tcp -d "$ALLOWED_DB_CIDR" --dport 5432 -j ACCEPT
  fi
  if [[ -n "$ALLOWED_REDIS_CIDR" ]]; then
    run_cmd iptables -A "$CHAIN_V4" -p tcp -d "$ALLOWED_REDIS_CIDR" --dport 6379 -j ACCEPT
  fi
  if [[ -n "$ALLOWED_DNS_CIDR" ]]; then
    run_cmd iptables -A "$CHAIN_V4" -p udp -d "$ALLOWED_DNS_CIDR" --dport 53 -j ACCEPT
    run_cmd iptables -A "$CHAIN_V4" -p tcp -d "$ALLOWED_DNS_CIDR" --dport 53 -j ACCEPT
  fi
  if [[ -n "$DOCKER_EGRESS_BRIDGE" ]]; then
    # Permit Docker embedded DNS resolver (127.0.0.11:53) before blocking 127.0.0.0/8 loopback
    run_cmd iptables -A "$CHAIN_V4" -p udp -d 127.0.0.11/32 --dport 53 -j ACCEPT
    run_cmd iptables -A "$CHAIN_V4" -p tcp -d 127.0.0.11/32 --dport 53 -j ACCEPT
  fi

  for cidr in "${BLOCKED_IPV4_CIDRS[@]}"; do
    run_cmd iptables -A "$CHAIN_V4" -d "$cidr" -j REJECT --reject-with icmp-admin-prohibited
  done
  run_cmd iptables -A "$CHAIN_V4" -p tcp --dport 443 -j ACCEPT
  run_cmd iptables -A "$CHAIN_V4" -p tcp --dport 80 -j ACCEPT
  run_cmd iptables -A "$CHAIN_V4" -j DROP

  # Attach to API worker UID egress in OUTPUT chain (native host worker)
  if [[ "$MODE" == "--dry-run" ]]; then
    printf 'iptables -C OUTPUT -m owner --uid-owner %s -j %s || iptables -I OUTPUT 1 -m owner --uid-owner %s -j %s\n' \
      "$WORKER_UID" "$CHAIN_V4" "$WORKER_UID" "$CHAIN_V4"
    if [[ -n "$DOCKER_EGRESS_BRIDGE" ]]; then
      printf 'iptables -C DOCKER-USER -i %s -j %s || iptables -I DOCKER-USER 1 -i %s -j %s\n' \
        "$DOCKER_EGRESS_BRIDGE" "$CHAIN_V4" "$DOCKER_EGRESS_BRIDGE" "$CHAIN_V4"
    fi
  else
    iptables -C OUTPUT -m owner --uid-owner "$WORKER_UID" -j "$CHAIN_V4" 2>/dev/null || \
      iptables -I OUTPUT 1 -m owner --uid-owner "$WORKER_UID" -j "$CHAIN_V4"
    if [[ -n "$DOCKER_EGRESS_BRIDGE" ]]; then
      iptables -C DOCKER-USER -i "$DOCKER_EGRESS_BRIDGE" -j "$CHAIN_V4" 2>/dev/null || \
        iptables -I DOCKER-USER 1 -i "$DOCKER_EGRESS_BRIDGE" -j "$CHAIN_V4"
    fi
  fi

  # IPv6 chain setup
  run_cmd ip6tables -N "$CHAIN_V6" 2>/dev/null || true
  run_cmd ip6tables -F "$CHAIN_V6"
  run_cmd ip6tables -A "$CHAIN_V6" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

  for cidr6 in "${BLOCKED_IPV6_CIDRS[@]}"; do
    run_cmd ip6tables -A "$CHAIN_V6" -d "$cidr6" -j REJECT --reject-with adm-prohibited
  done
  run_cmd ip6tables -A "$CHAIN_V6" -p tcp --dport 443 -j ACCEPT
  run_cmd ip6tables -A "$CHAIN_V6" -p tcp --dport 80 -j ACCEPT
  run_cmd ip6tables -A "$CHAIN_V6" -j DROP

  if [[ "$MODE" == "--dry-run" ]]; then
    printf 'ip6tables -C OUTPUT -m owner --uid-owner %s -j %s || ip6tables -I OUTPUT 1 -m owner --uid-owner %s -j %s\n' \
      "$WORKER_UID" "$CHAIN_V6" "$WORKER_UID" "$CHAIN_V6"
    if [[ -n "$DOCKER_EGRESS_BRIDGE" ]]; then
      printf 'ip6tables -L DOCKER-USER -n >/dev/null 2>&1 && (ip6tables -C DOCKER-USER -i %s -j %s || ip6tables -I DOCKER-USER 1 -i %s -j %s)\n' \
        "$DOCKER_EGRESS_BRIDGE" "$CHAIN_V6" "$DOCKER_EGRESS_BRIDGE" "$CHAIN_V6"
    fi
  else
    ip6tables -C OUTPUT -m owner --uid-owner "$WORKER_UID" -j "$CHAIN_V6" 2>/dev/null || \
      ip6tables -I OUTPUT 1 -m owner --uid-owner "$WORKER_UID" -j "$CHAIN_V6"
    if [[ -n "$DOCKER_EGRESS_BRIDGE" ]] && ip6tables -L DOCKER-USER -n >/dev/null 2>&1; then
      ip6tables -C DOCKER-USER -i "$DOCKER_EGRESS_BRIDGE" -j "$CHAIN_V6" 2>/dev/null || \
        ip6tables -I DOCKER-USER 1 -i "$DOCKER_EGRESS_BRIDGE" -j "$CHAIN_V6"
    fi
  fi
}

verify_rules() {
  preflight_live
  iptables -L "$CHAIN_V4" -n -v
  ip6tables -L "$CHAIN_V6" -n -v
  if [[ -n "$DOCKER_EGRESS_BRIDGE" ]]; then
    iptables -L DOCKER-USER -n -v
  fi
}

case "$MODE" in
  --dry-run|--apply)
    apply_rules
    ;;
  --verify)
    verify_rules
    ;;
  *)
    echo "Unknown mode: $MODE (expected --dry-run, --apply, or --verify)" >&2
    exit 1
    ;;
esac
