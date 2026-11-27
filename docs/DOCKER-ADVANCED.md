# Docker: advanced

Everything the desktop app does, headless in Docker Compose: SSH tunnels, rule-based routing, HTTPS inspection, egress sandboxes, and pools of proxies that **scale out behind HAProxy, with replicas discovered through Docker's DNS**. Each pattern is a runnable project in [`examples/`](../examples/), tested by [`examples/smoke-test.sh`](../examples/smoke-test.sh).

- Back to [README](../README.md) · [Docker: basics](DOCKER-BASIC.md) · [Advanced use cases](USE-CASES-ADVANCED.md)

> For development, testing, labs, and homelabs. **None of this is a production deployment guide.** There is no inbound authentication, so publish ports on `127.0.0.1` or keep them on private networks.

---

## 1. Every GUI feature as Compose

The [desktop app](https://github.com/jpbaking/rusty-conduit-gui) embeds the same engine as the CLIs, so each of its features has a container equivalent:

| In the GUI | In Compose | Example |
| :--- | :--- | :--- |
| A **Proxy** in Direct mode | A `rusty-conduit` service | [`direct`](../examples/direct/compose.yaml) |
| Proxy → **upstream proxy** (HTTP, HTTPS, SOCKS5, SOCKS4a, with credentials) | `rusty-conduit-switch` with a profile and `default = "<profile>"`; credentials via `password_env` or `password_file` | [`switch`](../examples/switch/) |
| Proxy → **Tunnel** | A `rusty-conduit-ssh` service; or a switch profile `type = "socks5"` pointing at it | [`ssh-tunnel`](../examples/ssh-tunnel/compose.yaml), [`homelab-stack`](../examples/homelab-stack/) |
| **Auto Switch** rules and failover chains | `[[routing.rules]]` and list targets in the switch config | [`switch`](../examples/switch/conf/config.toml) |
| **Route Tester** | `docker compose run --rm --no-deps switch test-route --config … <host:port>` | [`switch`](../examples/switch/compose.yaml) |
| Hot reload on save; **External TOML** mode | A mounted config directory plus `--watch-config`, or `docker compose kill -s HUP` | [`switch`](../examples/switch/compose.yaml) |
| Several Proxies running at once | Several services on different host ports | — |
| **Start All**, autostart, reconnect | `restart: unless-stopped`; `rusty-conduit-ssh` restarts `ssh` with backoff | all |
| Tunnel **jump chain** | `ProxyJump` in the mounted `ssh/config`, or `-J host1,host2` | [section 2](#2-ssh-tunnels-in-containers) |
| Tunnel **port forwards** (local and remote) | `ssh` arguments after `--`: `-L 0.0.0.0:8080:host:80` (and publish `8080`), `-R 127.0.0.1:9000:host:80` | [`ssh-tunnel`](../examples/ssh-tunnel/compose.yaml) |
| Tunnel **reverse proxy** | `--reverse-http-port`, `--reverse-socks-port`, `--reverse-block` | [`ssh-tunnel`](../examples/ssh-tunnel/compose.yaml) |
| **Host-key pinning** | A checked `known_hosts` file, mounted read-only | [`ssh-tunnel`](../examples/ssh-tunnel/compose.yaml) |
| **Encrypted vault** | Compose secrets at `/run/secrets/…`, or environment variables | [section 3](#3-https-inspection-in-containers) |
| **MITM** with your CA, insecure lab hosts | CA as secrets; `*_MITM_CA_CERT`, `*_MITM_CA_KEY`, `--mitm-insecure-host` | [`homelab-stack/compose.mitm.yaml`](../examples/homelab-stack/compose.mitm.yaml) |
| Global **allow / block** filter, block web over SOCKS | `--allow`, `--block`, `--socks-block-web` | [`egress-sandbox`](../examples/egress-sandbox/compose.yaml) |
| Tray **override** (force one profile for a while) | Change `default` (or a rule) and save: every replica hot-reloads. Or run a second switch service on another port with its own config | — |
| AirSwitch / ZeroOmega **import** | `docker run --rm -v "$PWD/conf:/work" ghcr.io/jpbaking/rusty-conduit-switch:2 import-airswitch /work/OmegaOptions.bak > conf/config.toml` | — |
| Import / export CLI `config.toml` | The exported files mount straight into the containers | — |
| Logs window | `docker compose logs -f <service>`, `--log-format json` | all |

What Compose adds that the GUI does not have: **horizontal scale**. Several identical replicas sit behind HAProxy, the pool grows or shrinks with `--scale`, and an unhealthy replica drops out on its own ([section 4](#4-scale-out-with-haproxy-and-docker-dns)).

## 2. SSH tunnels in containers

Project: [`examples/ssh-tunnel`](../examples/ssh-tunnel/compose.yaml)

The project runs a lab SSH server on a private `lab-lan` network that only the server can reach, a web service on that network, and `rusty-conduit-ssh` in front:

```sh
cd examples/ssh-tunnel
docker compose up -d --build
curl -x http://127.0.0.1:3128 http://internal-web/          # through SSH, resolved on the server
curl --socks5-hostname 127.0.0.1:1080 http://internal-web/
curl http://127.0.0.1:8080/                                 # the ssh -L port forward
docker compose exec sshd curl -sx http://127.0.0.1:8888 https://example.com/ -o /dev/null -w '%{http_code}\n'   # reverse proxy
docker compose restart sshd                                 # the tunnel reconnects on its own
```

A one-shot `keygen` service writes the keys, a pinned `known_hosts`, and the SSH `config` into a Docker volume. They are owned by UID `10001` from the start, so the setup works on any Docker host without `chown`.

### Use your own server

Replace the `keygen`, `sshd`, and `internal-web` services with a directory of real SSH files:

```sh
mkdir -p ssh && chmod 700 ssh
ssh-keygen -t ed25519 -N '' -C rusty-conduit-ssh -f ssh/id_ed25519   # add the .pub to the server's authorized_keys
ssh-keyscan -t ed25519 bastion.example.com > ssh/known_hosts          # then compare the fingerprint
cat > ssh/config <<'EOF'
Host my-bastion
    HostName bastion.example.com
    User deploy
    IdentityFile /ssh/id_ed25519
    UserKnownHostsFile /ssh/known_hosts
    BatchMode yes
    UpdateHostKeys no
    # ProxyJump jump.example.com      # multi-hop, like the GUI's jump chain
EOF
chmod 600 ssh/*
```

```yaml
services:
  tunnel:
    image: ghcr.io/jpbaking/rusty-conduit-ssh:2
    restart: unless-stopped
    user: "1000:1000"            # Linux: your id -u:id -g, so ssh can read your files
    command: ["my-bastion", "-F", "/ssh/config"]
    ports: ["127.0.0.1:3128:3128", "127.0.0.1:1080:1080"]
    volumes: ["./ssh:/ssh:ro"]
    read_only: true
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
```

- **Use absolute paths** in the `config`, plus `BatchMode yes`: nobody can answer a prompt in a container.
- **A server on the Docker host** is `host.docker.internal` (on Linux, add `extra_hosts: ["host.docker.internal:host-gateway"]`).
- **`ssh-agent` instead of a key file** and other variations are in the [rusty-conduit-ssh Docker Guide](https://github.com/jpbaking/rusty-conduit-ssh/blob/main/docs/DOCKER-GUIDE.md).
- **Health:** listeners open only after the first successful login, so a TCP health check turns healthy once SSH works. Later drops keep the listeners open while `ssh` reconnects; alert on `SSH tunnel down` in the logs.
- **Reverse proxy and remote forwards:** the server decides the final bind address. Use `GatewayPorts clientspecified` in its `sshd_config` (the lab does), and keep the `--reverse-block` list.

## 3. HTTPS inspection in containers

Project: [`examples/homelab-stack/compose.mitm.yaml`](../examples/homelab-stack/compose.mitm.yaml)

Create a dedicated CA. This runs `openssl` in a container, so it works the same on every host (macOS's built-in LibreSSL lacks `-noenc`):

```sh
cd examples/homelab-stack
mkdir -p secrets
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD/secrets:/out" -w /out alpine/openssl \
  req -x509 -new -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -noenc \
  -keyout ca.key -out ca.pem -days 825 \
  -subj "/CN=Rusty Conduit Lab CA/O=Homelab" \
  -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -addext "subjectKeyIdentifier=hash"
chmod 600 secrets/ca.key
```

Turn it on with the override file, which passes the CA as Compose secrets through environment variables, so the service's `command` stays unchanged:

```yaml
services:
  switch:
    environment:
      RUSTY_CONDUIT_SWITCH_MITM_CA_CERT: /run/secrets/ca_cert
      RUSTY_CONDUIT_SWITCH_MITM_CA_KEY: /run/secrets/ca_key
    secrets: [ca_cert, ca_key]

secrets:
  ca_cert: { file: ./secrets/ca.pem }
  ca_key: { file: ./secrets/ca.key }
```

```sh
docker compose -f compose.yaml -f compose.mitm.yaml up -d --build
curl --cacert secrets/ca.pem -x http://127.0.0.1:3128 https://www.example.com/
docker compose logs switch | grep mitm=true          # full URLs and status codes
```

- **Linux hosts:** Compose secrets are bind mounts, so `ca.key` must be readable by UID `10001`: `sudo chown 10001 secrets/ca.key`, or set `user:` on the service.
- **Every replica shares the CA,** so clients trust the whole pool as one proxy.
- `secrets/` is gitignored in this repo. Never bake a CA key into an image.
- For self-signed lab origins, add `RUSTY_CONDUIT_SWITCH_MITM_INSECURE_HOST: "*.lab.internal,10.20.0.0/16"`. For PKCS#12 or an encrypted key, see the product's [MITM CA Guide](https://github.com/jpbaking/rusty-conduit-switch/blob/main/docs/MITM-CA-GUIDE.md).

## 4. Scale out with HAProxy and Docker DNS

Project: [`examples/scale-out`](../examples/scale-out/)

```text
clients ──► haproxy :3128 / :1080 ──► proxy-1
                 │  (leastconn)   ├──► proxy-2
                 │                └──► proxy-N      docker compose up -d --scale proxy=N
                 └── :8404 stats
```

```sh
cd examples/scale-out
docker compose up -d                      # 3 replicas (deploy.replicas)
docker compose up -d --scale proxy=5      # HAProxy picks up the new ones within seconds
curl -x http://127.0.0.1:3128 https://example.com/
open http://127.0.0.1:8404/               # one row per replica, with health and connections
```

### How discovery works

Docker's embedded DNS server (`127.0.0.11`, inside every container on a user-defined network) answers a service name with one A record per running replica. HAProxy re-resolves it and fills a fixed set of server slots:

```haproxy
resolvers docker
    nameserver dns 127.0.0.11:53
    accepted_payload_size 8192
    hold valid 5s                 # re-resolve every few seconds

backend pool_http
    balance leastconn             # proxy connections vary widely in length
    server-template proxy 10 proxy:3128 check inter 2s resolvers docker init-addr none
```

- **`server-template proxy 10`** reserves ten slots. Replicas beyond ten are ignored, so raise the number to scale further.
- **`init-addr none`** lets HAProxy start before any replica exists. Empty slots show as `MAINT` on the stats page.
- **`check`** opens a TCP connection every 2 s, and a replica that stops accepting leaves the pool. For `rusty-conduit-ssh` replicas, this also keeps out a replica whose first SSH login has not succeeded yet.
- **Mode `tcp`:** HAProxy forwards bytes and never parses HTTP, `CONNECT`, or SOCKS, so every protocol, single-port multiplexing, and MITM pass through unchanged.

### Timeouts and keepalive

```haproxy
defaults
    timeout connect 5s
    timeout client 24h            # inactivity timeouts; proxies carry long silent tunnels
    timeout server 24h
    option clitcpka               # TCP keepalive on both sides, like the proxies themselves
    option srvtcpka
```

HAProxy's defaults of a few seconds or minutes would cut idle `CONNECT` tunnels, long polls, and SSH sessions that the proxies themselves keep open indefinitely.

### Things to know before you scale

- **Every replica must be identical:** same image, flags, config, and CA. Mount one config directory into all of them. With `--watch-config`, each replica reloads on its own.
- **The proxies see HAProxy's address, not the client's,** so access logs show HAProxy's container IP. Use HAProxy's own `tcplog` lines to see the real client.
- **No session affinity is needed.** Every connection is independent, and nothing is cached in a replica, apart from MITM leaf certificates, which each replica mints from the shared CA.
- **SSH replicas each hold their own SSH connection.** The server sees N logins. Do not give scaled tunnel replicas reverse ports or `-R` forwards: they would all ask the server for the same remote port.
- **Removing a replica drops its connections.** They are not moved; clients reconnect and HAProxy sends them to the replicas that remain. Scale down when the pool is quiet.
- **One host only:** Compose replicas and Docker DNS work within one Docker host. Spreading across hosts is a job for an orchestrator, outside this guide.

## 5. An egress sandbox network

Project: [`examples/egress-sandbox`](../examples/egress-sandbox/compose.yaml)

Put an agent, a CI job, or an untrusted build on an `internal: true` network with no gateway. Its only way out is a proxy that allows listed destinations and logs every attempt:

```yaml
services:
  egress-proxy:
    image: ghcr.io/jpbaking/rusty-conduit:2
    command: ["--allow", "github.com,*.github.com,*.githubusercontent.com,pypi.org,files.pythonhosted.org,registry.npmjs.org",
              "--log-level", "DEBUG", "--log-format", "json"]
    networks: [sandbox, internet]

  agent:
    image: curlimages/curl:latest
    entrypoint: ["sleep", "infinity"]
    environment:
      https_proxy: http://egress-proxy:3128
      HTTPS_PROXY: http://egress-proxy:3128
    networks: [sandbox]

networks:
  sandbox:
    internal: true
  internet:
```

```sh
cd examples/egress-sandbox
docker compose up -d
docker compose exec agent curl -sI https://github.com/                  # allowed
docker compose exec agent curl -sI https://example.com/                 # 403 from the proxy
docker compose exec agent curl -sI --noproxy '*' https://example.com/   # no route out: times out
docker compose logs egress-proxy                                        # every attempt, as JSON
```

- **Use `--allow` alone.** With `--block` set too, `--allow` only makes exceptions to the blocklist, and everything else is allowed.
- `*.domain` in a filter matches subdomains only, so list `github.com` as well as `*.github.com`.
- `internal: true` networks also lose the host's published-port path, so reach the agent with `docker compose exec`.

## 6. The homelab stack

Project: [`examples/homelab-stack`](../examples/homelab-stack/)

Everything together: one entry point, rule-based routing, and two kinds of egress pool, each scaled independently.

```text
                         ┌──────────────── haproxy ────────────────┐
clients ──► :3128/:1080 ─┤ front ──► switch ×N ──rules──► direct   │
                         │                      ├──► block          │
            :8404 stats  │ :13128 ◄─────────────┤  (egress profile) ├──► egress ×N ──► internet
                         │ :11080 ◄─────────────┘  (tunnel profile) ├──► tunnel ×N ──► ssh ──► lab-lan
                         └─────────────────────────────────────────┘
```

```sh
cd examples/homelab-stack
docker compose up -d --build
curl -x http://127.0.0.1:3128 http://internal-web/        # rule lab-via-tunnel → tunnel pool → SSH
curl -x http://127.0.0.1:3128 https://www.example.com/    # rule example-via-egress → egress pool
curl -x http://127.0.0.1:3128 https://github.com/         # default → direct from a switch replica
docker compose up -d --scale switch=3 --scale tunnel=3
docker compose stop egress                                # example.com fails over to the tunnel pool
```

The switch config ([`conf/config.toml`](../examples/homelab-stack/conf/config.toml)) names each pool by HAProxy's internal frontends:

```toml
[profiles.egress]
type = "http"
host = "haproxy"
port = 13128

[profiles.tunnel]
type = "socks5"            # host names are resolved on the SSH server
host = "haproxy"
port = 11080

[[routing.rules]]
name = "example-via-egress"
host_wildcard = ["*.example.com"]
target = ["egress", "tunnel", "direct"]
```

To adapt it to a real homelab:

- **Tunnel pool:** remove `keygen`, `sshd`, and `internal-web`, and point `tunnel` at your server as in [section 2](#use-your-own-server).
- **Egress pool:** give the egress proxies a different way out than `direct`, such as a macvlan network on another VLAN or a second NIC. For a VPN, run the VPN client as its own service and the proxy inside its network namespace (`network_mode: "service:vpn"`), one proxy per VPN container, and point HAProxy at the VPN service's name. Otherwise, "egress" leaves the same way as `direct`.
- **Rules:** edit `conf/config.toml` and save; every switch replica reloads it.
- **Inspection:** add `-f compose.mitm.yaml` ([section 3](#3-https-inspection-in-containers)).
- **Exposure:** HAProxy is the only service with published ports. Keep them on `127.0.0.1`, or on a LAN address behind a firewall.

## 7. Troubleshooting

| Symptom | Cause and fix |
| :--- | :--- |
| HAProxy stats show every slot `MAINT` | The service name in `server-template` does not match, or no replica is running. Check `docker compose ps`. |
| New replicas never receive traffic | They are past the `server-template` slot count, or `hold valid` is long. Raise the count, keep `hold valid` at a few seconds. |
| Idle tunnels close after a while | A timeout in front of the proxy. Raise HAProxy's `timeout client` and `timeout server`. |
| Tunnel replicas restart in a loop | The SSH login fails (check `docker compose logs tunnel`), or several replicas request the same reverse port. |
| `Host key verification failed.` | `known_hosts` does not match the server. Rescan and compare the fingerprint. |
| `curl: (60) SSL certificate problem` with MITM on | The client does not trust your CA. Pass `--cacert secrets/ca.pem` or add it to the client's trust store. |
| `FATAL MITM setup failed: ... Permission denied` | UID `10001` cannot read `ca.key` on a Linux host. `sudo chown 10001 secrets/ca.key`, or set `user:`. |
| Smoke test: `Bind for 127.0.0.1:3128 failed` | Another example or proxy is running. `docker compose down` there first. |
