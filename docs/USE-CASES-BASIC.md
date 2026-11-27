# Basic use cases

Short recipes for the most common jobs, each with the tool to use and the commands to run. For every flag and key, follow the links to each product's own guide.

- Back to [README](../README.md) · [Advanced use cases](USE-CASES-ADVANCED.md) · [Docker: basics](DOCKER-BASIC.md)

> For development, testing, and homelabs. The proxies have no inbound authentication: keep them on `127.0.0.1` (the default) or a private network you control.

**Install** any CLI from its Releases page ([rusty-conduit](https://github.com/jpbaking/rusty-conduit/releases), [rusty-conduit-ssh](https://github.com/jpbaking/rusty-conduit-ssh/releases), [rusty-conduit-switch](https://github.com/jpbaking/rusty-conduit-switch/releases)) for Linux, macOS, or Windows on `amd64` or `arm64`. Or use the container images in [Docker: basics](DOCKER-BASIC.md), or build from a clone with `cargo install --path .`.

---

## 1. A local proxy for your browser and tools

**Tool:** `rusty-conduit`

```sh
rusty-conduit            # HTTP/HTTPS on 127.0.0.1:3128, SOCKS4/4a/5 on 127.0.0.1:1080
```

Point clients at it:

```sh
# Most CLI tools, SDKs, and package managers
export http_proxy=http://127.0.0.1:3128 https_proxy=http://127.0.0.1:3128
export HTTP_PROXY=$http_proxy HTTPS_PROXY=$https_proxy
export no_proxy=localhost,127.0.0.1 NO_PROXY=localhost,127.0.0.1

# Or SOCKS, with DNS resolved by the proxy
export ALL_PROXY=socks5h://127.0.0.1:1080

curl https://example.com/
```

- **Browsers:** set a manual HTTP proxy `127.0.0.1:3128` for HTTP and HTTPS, or SOCKS v5 `127.0.0.1:1080`. In Firefox, also tick **Proxy DNS when using SOCKS v5**.
- **One port for everything:** `rusty-conduit --http-port 8888 --socks-port 8888`. The first byte of each connection picks the protocol.
- **`curl` and SOCKS:** use `--socks5-hostname` or `socks5h://`. Plain `--socks5` resolves names locally before the proxy sees them.

More: [rusty-conduit Basic User Guide](https://github.com/jpbaking/rusty-conduit/blob/main/docs/USER-GUIDE-BASIC.md).

## 2. See what your tools are calling

**Tool:** any of the three CLIs

```sh
rusty-conduit --log-level DEBUG                       # one record per connection on stdout
rusty-conduit --log-level DEBUG --log-format json 2>/dev/null | jq .
```

Each record has the client, the target, the status, the bytes in each direction, and the duration. `rusty-conduit-switch` also logs the rule, profile, and upstream it chose. To keep records in files, add `--http-access-log access.log --socks-log socks.log`.

HTTPS stays encrypted, so you see host names and ports, not URLs. To see full URLs and status codes for HTTPS, turn on [HTTPS inspection](USE-CASES-ADVANCED.md#3-inspect-https-with-your-own-ca).

## 3. Block destinations, or allow only a few

**Tool:** any of the three CLIs

```sh
# Block an ad network and the cloud metadata address
rusty-conduit --block "*.doubleclick.net,169.254.169.254"

# Allow only these destinations; everything else gets 403 (HTTP) or a SOCKS rejection
rusty-conduit --allow "github.com,*.github.com,*.githubusercontent.com,pypi.org,files.pythonhosted.org"
```

Entries are IPs, CIDRs, exact host names, or `*.domain` wildcards. In these filters `*.domain` matches subdomains only, so list the bare domain too if you need it (unlike switch routing rules, where `*.example.com` also matches `example.com`). Both host names and their resolved IPs are checked before connecting. With `--block` and `--allow` together, `--allow` carves out exceptions to the blocklist.

## 4. Reach your homelab or a private network over SSH

**Tool:** `rusty-conduit-ssh`

It runs your system `ssh`, so `~/.ssh/config`, `ssh-agent`, `ProxyJump`, FIDO2 keys, and password or 2FA prompts all work as usual:

```sh
rusty-conduit-ssh my-bastion                 # any ssh destination: an alias, a host, user@host
rusty-conduit-ssh deploy@203.0.113.10 -p 2222 -i ~/.ssh/id_ed25519
```

The listeners open once the tunnel is ready. Every connection, and every DNS lookup for a proxied host, goes through the SSH server, so names that only resolve there work:

```sh
curl --socks5-hostname 127.0.0.1:1080 http://nas.home.internal:5000/
curl -x http://127.0.0.1:3128 https://grafana.home.internal/
```

If the link drops, `ssh` restarts with backoff while the listeners stay open. More: [rusty-conduit-ssh Basic User Guide](https://github.com/jpbaking/rusty-conduit-ssh/blob/main/docs/USER-GUIDE-BASIC.md).

## 5. Send some sites through another proxy, and the rest direct

**Tool:** `rusty-conduit-switch`

```toml
# config.toml
[profiles.office]
type = "http"
host = "proxy.office.example"
port = 3128
username = "me"
password_env = "OFFICE_PROXY_PASS"     # or password_file; keep secrets out of the file

[profiles.homelab]
type = "socks5"                        # e.g. a rusty-conduit-ssh or ssh -D listener
host = "127.0.0.1"
port = 1081

[routing]
default = "direct"

[[routing.rules]]
name = "office-sites"
host_wildcard = ["*.office.example", "*.jira.example"]
target = "office"

[[routing.rules]]
name = "home-net"
cidr = ["192.168.1.0/24"]
target = "homelab"

[[routing.rules]]
name = "home-names"
host_wildcard = ["*.home.internal"]
target = "homelab"
```

```sh
rusty-conduit-switch validate --config config.toml
rusty-conduit-switch test-route --config config.toml nas.home.internal:5000   # which rule, profile, and upstream
rusty-conduit-switch --config config.toml --watch-config                       # edits apply without a restart
```

Rules run top to bottom and the first match wins. Within one rule, every field must match, which is why `cidr` and `host_wildcard` sit in separate rules above. More: [rusty-conduit-switch Basic User Guide](https://github.com/jpbaking/rusty-conduit-switch/blob/main/docs/USER-GUIDE-BASIC.md).

## 6. Bring your browser-extension rules

**Tool:** `rusty-conduit-switch` (or the GUI's import)

Export a backup from AirSwitch, ZeroOmega, or SwitchyOmega (**Import/Export → Backup**), then:

```sh
rusty-conduit-switch import-airswitch OmegaOptions.bak -o config.toml
rusty-conduit-switch validate --config config.toml
```

The output is commented TOML. Browser-only items such as PAC scripts are skipped, with a warning.

## 7. Do it all from a tray icon

**Tool:** [Rusty Conduit GUI](https://github.com/jpbaking/rusty-conduit-gui) *(beta)*

The desktop app saves **Proxies** (local listeners) and **Tunnels** (SSH connections, including multi-hop jump chains and port forwards) and runs, autostarts, and reconnects them for you. A Proxy's traffic can go direct, through an upstream proxy or a Tunnel, or wherever **Auto Switch** rules send it, and its Route Tester shows which rule a host would match. Secrets stay in an encrypted vault, and the app never reads or writes `~/.ssh`. It imports and exports the CLIs' `config.toml` files, so a setup can move between the app and a server.

Every one of those setups can also run headless in Docker: see [Docker: advanced](DOCKER-ADVANCED.md#1-every-gui-feature-as-compose).

---

## Where next

- [Advanced use cases](USE-CASES-ADVANCED.md): failover, time-based rules, HTTPS inspection, reverse proxies, jump hosts, and egress sandboxes.
- [Docker: basics](DOCKER-BASIC.md): the same recipes as containers.
