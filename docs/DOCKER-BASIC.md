# Docker: basics

Run the three CLIs as containers with `docker run` and Docker Compose: the images, a proxy for your host and for other containers, config files, hot reload, logs, and hardening. Every Compose file here is a runnable project in [`examples/`](../examples/).

- Back to [README](../README.md) · [Docker: advanced](DOCKER-ADVANCED.md) · [Basic use cases](USE-CASES-BASIC.md)

> For development, testing, and homelabs. There is no inbound authentication: **publish ports on `127.0.0.1`** unless a firewall guards them.

Each product has a full Docker guide with every option: [rusty-conduit](https://github.com/jpbaking/rusty-conduit/blob/main/docs/DOCKER-GUIDE.md), [rusty-conduit-ssh](https://github.com/jpbaking/rusty-conduit-ssh/blob/main/docs/DOCKER-GUIDE.md), and [rusty-conduit-switch](https://github.com/jpbaking/rusty-conduit-switch/blob/main/docs/DOCKER-GUIDE.md).

---

## 1. The images

| Image | Runs | Extra packages |
| :--- | :--- | :--- |
| `ghcr.io/jpbaking/rusty-conduit` | the direct proxy | `ca-certificates` |
| `ghcr.io/jpbaking/rusty-conduit-ssh` | the SSH-tunnel proxy | `ca-certificates`, `openssh-client` |
| `ghcr.io/jpbaking/rusty-conduit-switch` | the rule-based switch | `ca-certificates` |

All three share the same layout:

- **Tags:** `X.Y.Z`, `X.Y`, `X`, and `latest`. Pin the major tag (`:2`) to get fixes without breaking changes.
- **Platforms:** `linux/amd64` and `linux/arm64`, on Ubuntu 26.04 LTS.
- **User:** UID and GID `10001`, never root. No Linux capabilities are needed.
- **Entrypoint:** the binary. Anything after the image name is passed to it as arguments.
- **Ports:** `3128` (HTTP/HTTPS) and `1080` (SOCKS4/4a/5).
- **Environment:** `<PREFIX>_BIND=0.0.0.0` so Docker can forward to the listeners, and `MALLOC_ARENA_MAX=2` to keep memory low. Keep both.
- **Tools inside:** `bash`, but no `curl` or `nc`. Health checks use `bash`'s `/dev/tcp`.

The `SECURITY NOTICE: binding to non-loopback address 0.0.0.0` at startup is expected. Exposure is decided by the host side of `-p`, so `-p 127.0.0.1:3128:3128` keeps the proxy on your machine.

## 2. One-line runs

```sh
# Direct proxy
docker run --rm -p 127.0.0.1:3128:3128 -p 127.0.0.1:1080:1080 ghcr.io/jpbaking/rusty-conduit:2

# Same, on one port for both protocols
docker run --rm -p 127.0.0.1:8888:8888 ghcr.io/jpbaking/rusty-conduit:2 --http-port 8888 --socks-port 8888

# Switch with a config directory and hot reload
docker run --rm -p 127.0.0.1:3128:3128 -p 127.0.0.1:1080:1080 \
  -v "$PWD/conf:/etc/rusty-conduit-switch:ro" ghcr.io/jpbaking/rusty-conduit-switch:2 \
  --config /etc/rusty-conduit-switch/config.toml --watch-config

# SSH tunnel: give the container a key, known_hosts, and an ssh config (see Docker: advanced)
docker run --rm -p 127.0.0.1:3128:3128 -p 127.0.0.1:1080:1080 \
  -v "$PWD/ssh:/ssh:ro" ghcr.io/jpbaking/rusty-conduit-ssh:2 my-bastion -F /ssh/config
```

Flags work as on the host, and so do environment variables: `-e RUSTY_CONDUIT_LOG_LEVEL=DEBUG`, `-e RUSTY_CONDUIT_SSH_…`, `-e RUSTY_CONDUIT_SWITCH_…`.

## 3. A proxy for your host and your other containers

Project: [`examples/direct`](../examples/direct/compose.yaml)

```yaml
services:
  proxy:
    image: ghcr.io/jpbaking/rusty-conduit:2
    restart: unless-stopped
    command: ["--log-level", "DEBUG", "--block", "*.doubleclick.net,169.254.169.254"]
    ports:
      - "127.0.0.1:3128:3128"
      - "127.0.0.1:1080:1080"
    read_only: true
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    healthcheck:
      test: ["CMD", "bash", "-c", "exec 3<>/dev/tcp/127.0.0.1/3128"]
      interval: 30s
      timeout: 3s
      retries: 3

  app:
    image: curlimages/curl:latest
    command: ["-sS", "-o", "/dev/null", "-w", "%{http_code} via proxy\n", "https://example.com/"]
    environment:
      http_proxy: http://proxy:3128
      https_proxy: http://proxy:3128
      HTTPS_PROXY: http://proxy:3128
      no_proxy: localhost,127.0.0.1
    depends_on:
      proxy:
        condition: service_healthy
```

```sh
cd examples/direct
docker compose up -d
curl -x http://127.0.0.1:3128 https://example.com/
docker compose run --rm app            # prints: 200 via proxy
docker compose logs -f proxy           # one access record per connection
```

- **Containers reach the proxy by service name** (`proxy:3128`). To offer it only to containers, drop `ports:` entirely.
- **Set both spellings of the proxy variables.** Tools disagree: `curl` reads only lowercase `http_proxy` for `http://` URLs, while many SDKs read `HTTPS_PROXY`. For SOCKS, use `ALL_PROXY=socks5h://proxy:1080`.
- **Start in order:** the health check plus `condition: service_healthy` keeps clients from starting before the listener is up.

## 4. Config files

Mount a **directory** read-only and point `--config` at the file inside it, then check it with the same mounts before starting:

```sh
docker run --rm -v "$PWD/conf:/etc/rusty-conduit:ro" ghcr.io/jpbaking/rusty-conduit:2 \
  validate --config /etc/rusty-conduit/rusty-conduit.toml
```

`validate` also checks the files the config names (CA, password files, log paths) from inside the container. Add `--settings-only` to check just the settings. In Compose: `docker compose run --rm --no-deps <service> validate --config <path>`.

## 5. Rule-based routing with hot reload

Project: [`examples/switch`](../examples/switch/)

`rusty-conduit-switch` routes `*.example.com` through an `office` proxy, falls back to `backup`, then to `direct`, and blocks a tracker domain. Two `rusty-conduit` containers stand in for real upstream proxies, so the project runs on its own:

```sh
cd examples/switch
docker compose up -d
curl -x http://127.0.0.1:3128 https://www.example.com/
docker compose logs office-proxy | grep CONNECT       # it went through the office proxy

docker compose stop office-proxy
curl -x http://127.0.0.1:3128 https://www.example.com/   # still works: failover to backup
docker compose logs switch | grep profile=backup

docker compose run --rm --no-deps switch test-route \
  --config /etc/rusty-conduit-switch/config.toml www.example.com:443
```

Edit `examples/switch/conf/config.toml` and save: the log shows `config reloaded generation=N`, and new connections use the new rules while open ones keep theirs. A bad edit logs an `ERROR` and the running config stays.

- **Mount the directory, not the file.** Many editors save by renaming a new file over the old one, which a single-file bind mount never sees.
- **Reload by signal:** `docker compose kill -s HUP switch`.
- **Profile hosts resolve inside the container.** Use service names for other containers, and `host.docker.internal` for something on the Docker host (on Linux, add `extra_hosts: ["host.docker.internal:host-gateway"]`). `127.0.0.1` is the container itself.
- **Passwords for upstream proxies:** use `password_env` with Compose `environment:`, or `password_file` with a Compose secret at `/run/secrets/<name>`.

## 6. Logs

- **Diagnostics** go to `stderr`, which `docker logs` shows.
- **Access records** also go to `stdout` at `--log-level DEBUG`, so `docker logs <name> 2>/dev/null` shows only them. Add `--log-format json` for NDJSON.
- **Log files:** mount a named volume at `/var/log/<product>` (it belongs to UID `10001`) and pass `--http-access-log /var/log/<product>/access.log --socks-log /var/log/<product>/socks.log`.

## 7. Hardening and limits

Every example in this repo runs with:

```yaml
read_only: true
cap_drop: [ALL]
security_opt: ["no-new-privileges:true"]
```

- **Open files:** each proxy raises its limit at startup and needs `2 × max_connections + 64`. If it logs `NOTICE: open-file limit is ...`, add `ulimits: { nofile: 65536 }`.
- **CPU and memory:** one worker thread per CPU the container may use. `cpus: 2` also lowers idle memory; add `mem_limit` if you want a ceiling.
- **Stopping:** `docker stop` sends `SIGTERM` and open connections drain first.

## 8. File ownership on Linux hosts

Bind-mounted files keep their host owner, and the images never run as root, so they cannot fix ownership. This matters for SSH keys, CA keys, password files, and log directories:

| Host | Do this |
| :--- | :--- |
| Docker Desktop (macOS, Windows) | Nothing: ownership is mapped for you. |
| Linux, recommended | Run as yourself: `user: "1000:1000"` (your `id -u`:`id -g`). |
| Linux, image user | `sudo chown 10001 <file>`, keeping secrets at mode `600`. |

The SSH examples avoid the problem by generating their keys inside a Docker volume, owned by UID `10001` from the start.

## 9. Troubleshooting

| Symptom | Fix |
| :--- | :--- |
| Other machines cannot connect | Ports are published on `127.0.0.1`. Publish on a LAN address only behind a firewall: there is no authentication. |
| `Bind for 127.0.0.1:3128 failed` | Another process or example holds the port. Change the host side only, e.g. `127.0.0.1:8080:3128`. |
| Config edits are ignored | Mount the config directory, not the file. |
| An upstream profile at `127.0.0.1` fails | That is the container. Use the service name or `host.docker.internal`. |
| `Permission denied` on a key or log path | The container's UID cannot read or write it. See [section 8](#8-file-ownership-on-linux-hosts). |
| Memory far above the sizing guides | `MALLOC_ARENA_MAX` was overridden. Keep the image default of `2`. |

---

Next: [Docker: advanced](DOCKER-ADVANCED.md) has SSH tunnels in containers, every GUI feature as Compose, HTTPS inspection, egress sandboxes, and HAProxy scale-out.
