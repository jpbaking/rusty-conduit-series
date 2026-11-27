# Advanced use cases

Recipes that combine features: failover, rule tables, HTTPS inspection, reverse proxies, jump hosts, and egress sandboxes. They assume you have read the [basic use cases](USE-CASES-BASIC.md).

- Back to [README](../README.md) · [Basic use cases](USE-CASES-BASIC.md) · [Docker: advanced](DOCKER-ADVANCED.md)

> For development, testing, and homelabs, never as a promise of production readiness. No listener has inbound authentication, and HTTPS inspection decrypts traffic: use it only where you are allowed to.

Full references, one per product:

| Product | Reference |
| :--- | :--- |
| `rusty-conduit` | [Advanced User Guide](https://github.com/jpbaking/rusty-conduit/blob/main/docs/USER-GUIDE-ADVANCED.md) · [MITM CA Guide](https://github.com/jpbaking/rusty-conduit/blob/main/docs/MITM-CA-GUIDE.md) · [Sizing](https://github.com/jpbaking/rusty-conduit/blob/main/docs/PERFORMANCE-AND-SIZING.md) |
| `rusty-conduit-ssh` | [Advanced User Guide](https://github.com/jpbaking/rusty-conduit-ssh/blob/main/docs/USER-GUIDE-ADVANCED.md) · [MITM CA Guide](https://github.com/jpbaking/rusty-conduit-ssh/blob/main/docs/MITM-CA-GUIDE.md) · [Sizing](https://github.com/jpbaking/rusty-conduit-ssh/blob/main/docs/PERFORMANCE-AND-SIZING.md) |
| `rusty-conduit-switch` | [Advanced User Guide](https://github.com/jpbaking/rusty-conduit-switch/blob/main/docs/USER-GUIDE-ADVANCED.md) · [MITM CA Guide](https://github.com/jpbaking/rusty-conduit-switch/blob/main/docs/MITM-CA-GUIDE.md) · [Sizing](https://github.com/jpbaking/rusty-conduit-switch/blob/main/docs/PERFORMANCE-AND-SIZING.md) |

---

## 1. Failover chains

**Tool:** `rusty-conduit-switch`

Any `target` or `default` can be an ordered list:

```toml
[routing]
default = ["home-proxy", "direct"]

[[routing.rules]]
name = "work"
host_wildcard = ["*.corp.example"]
target = ["vpn", "ssh", "direct"]
```

- Profiles are tried in order, each bounded by `connect_timeout` (default `10s`; lower it so failover is quick).
- The next profile is tried only if the TCP connect or proxy handshake fails. A connection is never retried once bytes have flowed.
- `block` in a chain stops it. Logs show which profile served each connection, and failed attempts appear at `DEBUG`.

To spread load over several identical proxies, rather than fail over between them, put them behind HAProxy: see [Docker: advanced](DOCKER-ADVANCED.md#4-scale-out-with-haproxy-and-docker-dns).

## 2. Rules by protocol, port, time, and URL

**Tool:** `rusty-conduit-switch`

```toml
# Weekday office hours through the office proxy, otherwise direct
[[routing.rules]]
name = "office-hours"
host_wildcard = ["*.saas.example"]
weekday = ["mon-fri"]
time = ["08:30-18:00"]
target = "office"

# SSH and database ports through the bastion's SOCKS port
[[routing.rules]]
name = "admin-ports"
port = [22, 5432, "6379-6380"]
target = "bastion"

# SOCKS clients get their own table; HTTP clients keep the unified [routing] table
[routing.socks]
default = "bastion"
inherit = false
```

- **Every field in a rule must match** (AND); any value within a field may match (OR). Use separate rules for "this host *or* that subnet".
- **`cidr` / `ip` rules** match only IP literals unless you set `resolve_dns = true`, which resolves names locally and so reveals them to your local DNS server.
- **URL rules** (`url_wildcard`, `url_regex`, `keyword`) see URLs only for plain HTTP and for HTTPS decrypted by MITM, never for opaque `CONNECT` tunnels or SOCKS.
- **`composite` profiles** pick a different upstream for `http://`, `https://`, and everything else.

Check any destination before you rely on it:

```sh
rusty-conduit-switch test-route --config config.toml db.corp.example:5432
rusty-conduit-switch test-route --config config.toml --inbound socks api.saas.example:443
```

## 3. Inspect HTTPS with your own CA

**Tool:** any of the three CLIs

MITM is **off by default** and no tool ever creates a CA for you. Create a dedicated one (the [MITM CA Guide](https://github.com/jpbaking/rusty-conduit/blob/main/docs/MITM-CA-GUIDE.md) has the `openssl` commands, and [Docker: advanced](DOCKER-ADVANCED.md#3-https-inspection-in-containers) has a version that runs in a container), then:

```sh
rusty-conduit --mitm-ca-cert ca.pem --mitm-ca-key ca.key --log-level DEBUG
curl --cacert ca.pem -x http://127.0.0.1:3128 https://example.com/
```

- Access records now show each decrypted request's method, full URL, and status, with `mitm=true`. HTTP/1.1 and HTTP/2 are supported.
- Clients must trust `ca.pem`. Trust it per tool where you can (`curl --cacert`, `NODE_EXTRA_CA_CERTS`, `REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE`) rather than system-wide.
- With switch, MITM also enables URL rules on HTTPS, so requests on one tunnel can go to different upstreams.
- `--socks-block-web` refuses HTTP and HTTPS over SOCKS, so web traffic cannot dodge inspection by switching protocols.
- Protect the key: a dedicated CA, `chmod 600`, never in Git or an image. Remove the CA from every trust store when you are done.

## 4. Lab origins with self-signed certificates

**Tool:** any of the three CLIs, with MITM on

Under MITM the proxy verifies every upstream certificate strictly. For a lab whose services use self-signed certificates, skip verification for those hosts only:

```sh
rusty-conduit --mitm-ca-cert ca.pem --mitm-ca-key ca.key \
  --mitm-insecure-host "*.lab.internal,10.20.0.0/16"
```

Every other destination is still verified. `--mitm-insecure` trusts every upstream blindly; it is unsafe and logs a startup warning, so prefer the host list.

## 5. Give a remote machine internet through yours

**Tool:** `rusty-conduit-ssh` reverse proxy (`ssh -R`)

For a VM or box with no egress of its own, publish an HTTP and SOCKS proxy *on the SSH server* whose traffic leaves from your machine:

```sh
rusty-conduit-ssh build-box --reverse-http-port 8888 --reverse-socks-port 8888 \
  --reverse-block 127.0.0.0/8,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16
```

On the remote machine:

```sh
export https_proxy=http://127.0.0.1:8888
curl https://example.com/
```

- Anyone who can reach that port on the server can reach what your machine can reach, so keep `--reverse-bind 127.0.0.1` (the default) and the blocklist above.
- **The SSH server decides the final bind.** With `GatewayPorts yes` in its `sshd_config`, it listens on every interface even when you ask for loopback. Use `GatewayPorts clientspecified`.
- Add `--http-port 0 --socks-port 0` for a reverse-only proxy.

## 6. Jump hosts and port forwards

**Tool:** `rusty-conduit-ssh` (or GUI Tunnels)

Anything `ssh` can reach, `rusty-conduit-ssh` can proxy through:

```sh
rusty-conduit-ssh -J jump1.example.com,jump2.example.com deploy@inner.example.com

# Extra ssh arguments go after --, verbatim (they replace ssh.extra_args from the TOML)
rusty-conduit-ssh my-bastion -- -L 127.0.0.1:5432:db.internal:5432
```

`ProxyJump` in `~/.ssh/config` works too. The GUI builds the same chain visually, hop by hop, with its own SSH engine and host-key store.

## 7. An egress sandbox for agents, CI, and untrusted builds

**Tool:** `rusty-conduit` with an allowlist

Give an agent or a build exactly the destinations it needs, and log everything it tries:

```sh
rusty-conduit --allow "github.com,*.github.com,*.githubusercontent.com,registry.npmjs.org,pypi.org,files.pythonhosted.org" \
  --log-level DEBUG --log-format json --http-access-log egress.jsonl --socks-log egress-socks.jsonl
```

- Denied destinations get `403` (HTTP) or a SOCKS rejection, logged as `status=403` (HTTP) or `status=not_allowed` (SOCKS).
- An allowlist only helps if the client cannot bypass the proxy. In Docker, put the client on an `internal: true` network whose only way out is the proxy: [Docker: advanced](DOCKER-ADVANCED.md#5-an-egress-sandbox-network).
- **Use `--allow` on its own.** With `--block` also set, `--allow` only carves exceptions out of the blocklist and every other destination is allowed. An allowlist alone already denies cloud metadata (`169.254.169.254`) and your LAN unless you list them.

## 8. Long-lived and silent connections

All three CLIs have no idle timeout on established tunnels and turn on TCP keepalive on both sides (default `60s` idle, then `10s` × `5` probes), so NAT, firewalls, and VPNs keep long polls, streaming responses, and quiet agent sessions open. Tune with `--tcp-keepalive`, `--tcp-keepalive-interval`, and `--tcp-keepalive-retries`. For SSH, `--ssh-server-alive-interval` and `--ssh-server-alive-count-max` detect a dead tunnel. Anything in front of the proxy, such as HAProxy, needs long timeouts too.

## 9. Branded error pages

Replace the built-in HTML for errors the proxy itself returns (`403` from a filter, `502`, `504`, …):

```sh
rusty-conduit --error-page error.html     # placeholders: {{status}} {{reason}} {{message}} {{target}}
```

Responses from origin servers are never changed.

## 10. Sizing and limits

Each CLI raises its open-file limit at startup and needs about `2 × max_connections + 64` descriptors. Memory is about 7–8 MB idle plus 26–27 KB per open tunnel on Linux with `MALLOC_ARENA_MAX=2`, which the images set. When one instance is not enough, or you want rolling restarts, run several behind HAProxy: [Docker: advanced](DOCKER-ADVANCED.md#4-scale-out-with-haproxy-and-docker-dns). Each product's sizing guide has the measured figures.
