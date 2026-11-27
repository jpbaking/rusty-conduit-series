# examples

## Purpose
Runnable Docker Compose projects that back the claims in `README.md` and `docs/`. Audience: people evaluating or adopting the products, and agents adapting a setup.

## Ownership
Owns everything under `examples/`: one folder per Compose project, `lab/sshd/` (the lab SSH server image the SSH examples build), `smoke-test.sh`, and `README.md`. The prose guides are owned by the root doc. The products and their images are owned by the member repos.

## Local Contracts
- Every example runs on its own with `docker compose up -d` (plus `--build` where it uses `lab/sshd`). Stand-ins (lab sshd, stand-in upstreams, private web services) are part of the project.
- Use only published images: `ghcr.io/jpbaking/<product>:<major>` for the products, and pinned third-party images (`haproxy:3.2`, `alpine:3.22`) where a version matters.
- Publish ports on `127.0.0.1` only. Proxy services run with `read_only: true`, `cap_drop: [ALL]`, and `no-new-privileges`.
- Each example has a unique top-level `name:` (`rcs-<example>`) so Compose projects never collide.
- Each `compose.yaml` starts with a comment that says what it shows, that it is for dev and testing only, and the commands to try it.
- Never commit generated keys or CAs. SSH examples generate keys in a Docker volume (`lab/sshd/lab-keygen.sh`); MITM uses a gitignored `secrets/` folder.
- Adding, renaming, or removing an example updates `smoke-test.sh` (its `all=` list and a check block), `README.md` here, and every link to it from `README.md` and `docs/`.

## Verification
- `bash -n examples/smoke-test.sh` after any change to the script.
- `docker compose config -q` in each changed example.
- `examples/smoke-test.sh <example>` for each changed example must pass (needs Docker, `curl`, and internet access; uses host ports 1080, 3128, 8080, 8404).

## Feature Map
- **Direct proxy** — `rusty-conduit` with a blocklist and a container client. Start: `direct/compose.yaml`.
- **Rule-based switching** — rules, failover, `test-route`, hot reload against stand-in upstreams. Start: `switch/compose.yaml`. Files: `switch/conf/config.toml`.
- **Egress sandbox** — an internal-only network whose only route out is an allowlisting proxy. Start: `egress-sandbox/compose.yaml`.
- **SSH tunnel lab** — `rusty-conduit-ssh` into a private network, `-L` forward, reverse proxy. Start: `ssh-tunnel/compose.yaml`. Files: `lab/sshd/`.
- **HAProxy scale-out** — Docker DNS discovery with `server-template`, scaled replicas. Start: `scale-out/compose.yaml`. Files: `scale-out/haproxy.cfg`.
- **Homelab stack** — switch pool routing to egress and tunnel pools behind one HAProxy, optional MITM. Start: `homelab-stack/compose.yaml`. Files: `homelab-stack/haproxy.cfg`, `homelab-stack/conf/config.toml`, `homelab-stack/compose.mitm.yaml`, `lab/sshd/`.
- **Smoke test** — brings each example up, checks it, and tears it down. Start: `smoke-test.sh`.

## Child DOX Index
- (none)
