# rusty-conduit-series

**Small, fast HTTP/HTTPS and SOCKS proxies in single Rust binaries, plus a desktop app that runs them all.** Route traffic directly, through SSH, or through other proxies by rules. Run them on your laptop or in Docker, and scale them out behind HAProxy when one instance isn't enough.

> [!IMPORTANT]
> **For development, testing, labs, and homelabs.** These tools are well tested and built
> with care, but nothing here is promised to be production-ready, and the proxies have **no
> inbound authentication**. Keep them on loopback or a private network you control.

[Choose a tool](#pick-your-tool) · [Try it in 60 seconds](#try-it-in-60-seconds) · [Use cases](docs/USE-CASES-BASIC.md) · [Docker](docs/DOCKER-BASIC.md) · [Scale out](docs/DOCKER-ADVANCED.md) · [For agents](#for-ai-agents)

---

## Why people use it

- **One binary, every client protocol.** HTTP forwarding, HTTPS `CONNECT`, SOCKS4, SOCKS4a, and SOCKS5, on separate ports or **multiplexed on one port**. Browsers, `curl`, package managers, SDKs, and agents all just work.
- **SSH as an egress.** Point your tools at a local proxy and everything, DNS included, leaves through your bastion or homelab box. It auto-reconnects, and it can also share *your* connection with the remote host (`ssh -R`).
- **Rules, not toggles.** Send `*.corp.example` to the office proxy, the homelab subnet over SSH, ads to `block`, and the rest direct. Failover chains (`["vpn", "ssh", "direct"]`), time-of-day rules, and hot reload with no dropped connections. You can import AirSwitch, ZeroOmega, and SwitchyOmega backups.
- **See what your tools are doing.** Per-connection access logs (logfmt or JSON) name the rule, profile, and upstream each connection used. Opt-in HTTPS inspection with **your own CA**: none is ever auto-generated.
- **Light on resources.** About 7–8 MB of RAM idle and 26–27 KB per open tunnel, as measured on Linux with the container images' defaults. Nothing is cached, neither responses nor DNS, and long silent connections stay open.
- **Pure-Rust TLS.** `rustls` + `ring`, with no OpenSSL. Prebuilt for Linux, macOS, and Windows on `amd64` and `arm64`, plus multi-arch container images.
- **Point and click if you prefer.** The desktop app builds the same setups from a tray icon and a window, with an encrypted secret vault and no dependence on `~/.ssh`.

## Pick your tool

| You want to… | Use | Get it |
| :--- | :--- | :--- |
| Run a local HTTP/SOCKS proxy, with logging, allow/block lists, or HTTPS inspection | [**rusty-conduit**](https://github.com/jpbaking/rusty-conduit) | [Releases](https://github.com/jpbaking/rusty-conduit/releases) · `ghcr.io/jpbaking/rusty-conduit:2` |
| Send everything through an SSH server (bastion, homelab, cloud VM), or let that server egress through you | [**rusty-conduit-ssh**](https://github.com/jpbaking/rusty-conduit-ssh) | [Releases](https://github.com/jpbaking/rusty-conduit-ssh/releases) · `ghcr.io/jpbaking/rusty-conduit-ssh:2` |
| Route each connection by rules to different upstream proxies, with failover and hot reload | [**rusty-conduit-switch**](https://github.com/jpbaking/rusty-conduit-switch) | [Releases](https://github.com/jpbaking/rusty-conduit-switch/releases) · `ghcr.io/jpbaking/rusty-conduit-switch:2` |
| Do all of the above from a tray app, with saved Proxies and SSH Tunnels | [**Rusty Conduit GUI**](https://github.com/jpbaking/rusty-conduit-gui) *(beta)* | [Releases](https://github.com/jpbaking/rusty-conduit-gui/releases): `.dmg`, `.msi`/`.exe`, `.deb`, `.rpm`, `.AppImage` |
| Embed the engine in your own Rust program | [**rusty-conduit-engine**](https://github.com/jpbaking/rusty-conduit-engine) | Git dependency pinned to a release tag |

All five are BSD-3-Clause and share one engine, so a fix lands in every tool at once.

```text
                       ┌──────────────────────┐
  browser, curl,  ───► │ rusty-conduit        │ ───► internet
  SDKs, agents,        │ rusty-conduit-ssh    │ ───► ssh ───► bastion ───► private network
  containers           │ rusty-conduit-switch │ ───► rules ──► direct │ block │ proxy A │ proxy B │ …
                       └──────────────────────┘
                         HTTP · HTTPS · SOCKS4/4a/5 in; optional MITM with your CA
```

## Try it in 60 seconds

With Docker:

```sh
docker run --rm -p 127.0.0.1:3128:3128 -p 127.0.0.1:1080:1080 ghcr.io/jpbaking/rusty-conduit:2

# in another terminal
curl -x http://127.0.0.1:3128 https://example.com/
curl --socks5-hostname 127.0.0.1:1080 https://example.com/
```

Through SSH, with a [prebuilt binary](https://github.com/jpbaking/rusty-conduit-ssh/releases) and your normal `~/.ssh/config`:

```sh
rusty-conduit-ssh my-bastion
curl --socks5-hostname 127.0.0.1:1080 http://grafana.homelab.internal/   # resolved on the bastion
```

Or run a complete, self-contained lab with one command: an SSH server, a private network, rule-based routing, and HAProxy balancing scaled pools:

```sh
git clone https://github.com/jpbaking/rusty-conduit-series.git
cd rusty-conduit-series/examples/homelab-stack
docker compose up -d --build
curl -x http://127.0.0.1:3128 http://internal-web/     # reachable only through the SSH tunnel
open http://127.0.0.1:8404/                            # HAProxy stats: one row per replica
```

## Documentation

| Guide | What's inside |
| :--- | :--- |
| [**Basic use cases**](docs/USE-CASES-BASIC.md) | A proxy for your tools, watching traffic, blocking destinations, reaching a homelab over SSH, routing some sites elsewhere, importing browser-extension rules |
| [**Advanced use cases**](docs/USE-CASES-ADVANCED.md) | Failover chains, split and time-based rules, HTTPS inspection, lab origins with self-signed certs, reverse proxies, jump hosts, egress sandboxes for agents and CI |
| [**Docker: basics**](docs/DOCKER-BASIC.md) | Images, `docker run`, Compose, a proxy for other containers, config, hot reload, logs, and hardening |
| [**Docker: advanced**](docs/DOCKER-ADVANCED.md) | Every GUI feature as Compose, SSH tunnels in containers, MITM with secrets, **HAProxy scale-out with Docker DNS discovery**, and the full homelab stack |
| [**Examples**](examples/) | Five runnable Compose projects, and a smoke test that checks each one |
| [**Contributing and the agent workspace**](docs/WORKSPACE.md) | How this repo clones the five product repos and how to work across them with coding agents |

Every product repo also has its own complete reference: every flag, environment variable, and TOML key, plus sizing figures and a MITM CA guide. The guides here link to the right page in each.

## For AI agents

If you are an agent helping someone choose or set up a proxy:

1. Pick the tool with the table in [Pick your tool](#pick-your-tool). If the person wants rules, failover, or several upstreams, use `rusty-conduit-switch`; if SSH is involved, use `rusty-conduit-ssh`, or `rusty-conduit-switch` with a `rusty-conduit-ssh` upstream.
2. Start from the closest recipe in [`docs/`](docs/) or the closest project in [`examples/`](examples/), and adapt it instead of writing config from scratch. Check the result with `validate` (all three CLIs) and `test-route` (switch).
3. Keep listeners on `127.0.0.1`, or publish container ports as `127.0.0.1:PORT:PORT`. There is no proxy authentication.
4. Turn on HTTPS MITM only when the person asks for inspection, with a CA they create. Never generate or install a CA without asking first.
5. Describe the result as suitable for development and testing, not production.

To change the tools themselves, start your coding agent in a clone of this repo and read [`docs/WORKSPACE.md`](docs/WORKSPACE.md).

## Security at a glance

- **No inbound authentication** on any listener. Bind to loopback (the default) or a trusted private network.
- **MITM decrypts traffic.** Use it only on systems and traffic you are authorized to inspect, and protect the CA key.
- **A reverse proxy (`ssh -R`) exposes your network** to users of the SSH server. Keep its default loopback bind, set `GatewayPorts clientspecified` on the server, and add a blocklist.

## License

BSD-3-Clause. See [LICENSE](LICENSE).
