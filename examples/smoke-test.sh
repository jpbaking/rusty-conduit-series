#!/usr/bin/env bash
# Bring each example up, check what its docs promise, and tear it down again.
#
# Usage: examples/smoke-test.sh [EXAMPLE...]
#   EXAMPLE  direct, switch, egress-sandbox, ssh-tunnel, scale-out, homelab-stack
#            (default: all)
#
# Needs Docker with Compose v2, curl, and internet access (requests go to example.com).
# Uses host ports 127.0.0.1:1080, 3128, 8080, and 8404; set RCS_PORT_<port> to move any of them.
# Each example is removed afterwards, volumes included (docker compose down -v).
set -euo pipefail
# Host ports; override any of them to run beside a proxy you already have (RCS_PORT_3128=13128 ...).
p3128=${RCS_PORT_3128:-3128}
p1080=${RCS_PORT_1080:-1080}
p8080=${RCS_PORT_8080:-8080}
p8404=${RCS_PORT_8404:-8404}
export RCS_PORT_3128=$p3128 RCS_PORT_1080=$p1080 RCS_PORT_8080=$p8080 RCS_PORT_8404=$p8404

here=$(cd "$(dirname "$0")" && pwd)
all=(direct switch egress-sandbox ssh-tunnel scale-out homelab-stack)
[ "$#" -gt 0 ] && examples=("$@") || examples=("${all[@]}")
failures=0
current=""

pass() { echo "  ok    $1"; }
fail() { echo "  FAIL  $1" >&2; failures=$((failures + 1)); }

# expect DESCRIPTION WANT COMMAND...: run COMMAND, compare its stdout with WANT.
expect() {
  local what=$1 want=$2 got
  shift 2
  got=$("$@" 2>/dev/null || true)
  if [ "$got" = "$want" ]; then pass "$what"; else fail "$what (wanted '$want', got '$got')"; fi
}

# contains DESCRIPTION NEEDLE COMMAND...: COMMAND's stdout must contain NEEDLE.
contains() {
  local what=$1 needle=$2 got
  shift 2
  got=$("$@" 2>/dev/null || true)
  case $got in *"$needle"*) pass "$what" ;; *) fail "$what (no '$needle' in output)" ;; esac
}

code() { curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$@"; }
dc() { docker compose "$@"; }

# Count replicas HAProxy reports UP in BACKEND.
pool_up() {
  curl -s --max-time 5 "http://127.0.0.1:$p8404/;csv" |
    awk -F, -v b="$1" '$1 == b && $2 != "BACKEND" && $18 ~ /^UP/' | wc -l | tr -d ' '
}

# Wait up to 60 s for BACKEND to report WANT replicas UP.
wait_pool() {
  local i
  for i in $(seq 1 30); do
    [ "$(pool_up "$1")" = "$2" ] && return 0
    sleep 2
  done
  return 0
}

cleanup() {
  [ -n "$current" ] || return 0
  (cd "$here/$current" && dc down -v --remove-orphans >/dev/null 2>&1) || true
}
trap cleanup EXIT

for ex in "${examples[@]}"; do
  [ -f "$here/$ex/compose.yaml" ] || { echo "unknown example: $ex" >&2; exit 2; }
  echo "== $ex"
  current=$ex
  cd "$here/$ex"
  dc config -q

  case $ex in
    direct)
      dc up -d --wait >/dev/null 2>&1
      expect "HTTP proxy" 200 code -x http://127.0.0.1:$p3128 https://example.com/
      expect "SOCKS5 proxy" 200 code --socks5-hostname 127.0.0.1:$p1080 https://example.com/
      expect "blocklist" 403 code -x http://127.0.0.1:$p3128 http://ad.doubleclick.net/
      contains "container client" "200 via proxy" dc run --rm app
      ;;

    switch)
      cfg=/etc/rusty-conduit-switch/config.toml
      contains "validate" "config OK" dc run --rm --no-deps switch validate --config "$cfg"
      dc up -d --wait >/dev/null 2>&1
      contains "test-route" "profile=office" dc run --rm --no-deps switch test-route --config "$cfg" www.example.com:443
      expect "rule to office-proxy" 200 code -x http://127.0.0.1:$p3128 https://www.example.com/
      contains "office-proxy saw it" "CONNECT www.example.com" dc logs office-proxy
      dc stop office-proxy >/dev/null 2>&1
      expect "failover" 200 code -x http://127.0.0.1:$p3128 https://www.example.com/
      contains "failover used backup" "profile=backup" dc logs switch
      expect "block rule" 403 code -x http://127.0.0.1:$p3128 http://ad.doubleclick.net/
      ;;

    egress-sandbox)
      dc up -d --wait >/dev/null 2>&1
      expect "allowed destination" 200 dc exec -T agent curl -s -o /dev/null -w '%{http_code}' --max-time 20 https://github.com/
      expect "denied destination" 403 dc exec -T agent curl -s -o /dev/null -w '%{http_connect}' --max-time 20 https://example.com/
      expect "no bypass route" 000 dc exec -T agent curl -s -o /dev/null -w '%{http_code}' --noproxy '*' --max-time 5 https://example.com/
      contains "attempts logged" '"status":403' dc logs egress-proxy
      ;;

    ssh-tunnel)
      dc up -d --build --wait >/dev/null 2>&1
      contains "HTTP via SSH" "Hostname:" curl -s --max-time 20 -x http://127.0.0.1:$p3128 http://internal-web/
      contains "SOCKS5 via SSH" "Hostname:" curl -s --max-time 20 --socks5-hostname 127.0.0.1:$p1080 http://internal-web/
      contains "ssh -L forward" "Hostname:" curl -s --max-time 20 http://127.0.0.1:$p8080/
      expect "reverse proxy" 200 dc exec -T sshd curl -s -o /dev/null -w '%{http_code}' --max-time 20 -x http://127.0.0.1:8888 https://example.com/
      dc restart sshd >/dev/null 2>&1
      sleep 8
      contains "reconnect" "Hostname:" curl -s --max-time 20 -x http://127.0.0.1:$p3128 http://internal-web/
      ;;

    scale-out)
      dc up -d >/dev/null 2>&1
      wait_pool pool_http 3
      expect "3 replicas up" 3 pool_up pool_http
      expect "balanced HTTP" 200 code -x http://127.0.0.1:$p3128 https://example.com/
      expect "balanced SOCKS5" 200 code --socks5-hostname 127.0.0.1:$p1080 https://example.com/
      dc up -d --scale proxy=5 >/dev/null 2>&1
      wait_pool pool_http 5
      expect "scaled to 5" 5 pool_up pool_http
      dc up -d --scale proxy=2 >/dev/null 2>&1
      wait_pool pool_http 2
      expect "scaled to 2" 2 pool_up pool_http
      ;;

    homelab-stack)
      cfg=/etc/rusty-conduit-switch/config.toml
      dc up -d --build >/dev/null 2>&1
      wait_pool tunnel_pool 2
      wait_pool switch_http 2
      wait_pool egress_pool 2
      expect "switch pool up" 2 pool_up switch_http
      expect "egress pool up" 2 pool_up egress_pool
      expect "tunnel pool up" 2 pool_up tunnel_pool
      contains "lab host via tunnel" "Hostname:" curl -s --max-time 20 -x http://127.0.0.1:$p3128 http://internal-web/
      expect "site via egress" 200 code -x http://127.0.0.1:$p3128 https://www.example.com/
      expect "block rule" 403 code -x http://127.0.0.1:$p3128 http://ad.doubleclick.net/
      contains "test-route" "rule=lab-via-tunnel" dc run --rm --no-deps switch test-route --config "$cfg" internal-web:80
      dc stop egress >/dev/null 2>&1
      sleep 4
      expect "failover to tunnel" 200 code -x http://127.0.0.1:$p3128 https://www.example.com/
      ;;
  esac

  dc down -v --remove-orphans >/dev/null 2>&1
  current=""
done

if [ "$failures" -gt 0 ]; then
  echo "smoke-test: $failures check(s) failed" >&2
  exit 1
fi
echo "smoke-test: all checks passed"
