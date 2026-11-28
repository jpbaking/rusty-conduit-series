# phase-0001 — README example count, pinned example images, homelab pool waits

- Status: todo
- Owner: executor
- Depends on: none
- Goal: Correct the README's example count, pin the two unpinned third-party images, and make the `homelab-stack` smoke check wait for all three HAProxy pools before checking them.
- Done when: every command in `## Verify` exits 0.
- Pattern to follow: `examples/smoke-test.sh:113-114` (`wait_pool <backend> <n>` directly before the `expect ... pool_up <backend>` it guards)

## Context
`examples/` holds six Compose projects (`direct`, `switch`, `egress-sandbox`, `ssh-tunnel`, `scale-out`, `homelab-stack`), but `README.md:82` says five. `examples/DOX.md` requires pinned third-party images where a version matters; `traefik/whoami:latest` and `curlimages/curl:latest` are not pinned. The planner checked Docker Hub on 2026-11-28: the newest tags are `v1.12.0` and `8.23.0`.
`homelab-stack` waits only for `tunnel_pool`, then checks `switch_http` and `egress_pool` too, so a slow start reports a false failure. `wait_pool` returning 0 on timeout is deliberate; do not change it.
`site/index.html` gives no count, so it needs no change.

## Scope
- In: `README.md` (line 82 only), `examples/ssh-tunnel/compose.yaml`, `examples/homelab-stack/compose.yaml`, `examples/direct/compose.yaml`, `examples/egress-sandbox/compose.yaml`, `examples/smoke-test.sh` (the `homelab-stack)` block only), `examples/DOX.md` (the pinned-image Local Contract bullet only)
- Out: `site/`, `docs/`, every other example file, the `wait_pool` function body

## Sub-tasks
1. [todo] In `README.md` line 82, change `Five runnable Compose projects` to `Six runnable Compose projects` — done when: `grep -c 'Six runnable Compose projects' README.md` prints `1` and `grep -c 'Five runnable' README.md` prints `0`.
2. [todo] Replace `traefik/whoami:latest` with `traefik/whoami:v1.12.0` in `examples/ssh-tunnel/compose.yaml` and `examples/homelab-stack/compose.yaml`, and `curlimages/curl:latest` with `curlimages/curl:8.23.0` in `examples/direct/compose.yaml` and `examples/egress-sandbox/compose.yaml` — done when: `grep -rn ':latest' examples --include=compose*.yaml` prints nothing.
3. [todo] In the `homelab-stack)` block of `examples/smoke-test.sh`, directly after `      wait_pool tunnel_pool 2`, add the lines `      wait_pool switch_http 2` and `      wait_pool egress_pool 2` — done when: `grep -c 'wait_pool switch_http 2' examples/smoke-test.sh` and `grep -c 'wait_pool egress_pool 2' examples/smoke-test.sh` each print `1` and `bash -n examples/smoke-test.sh` exits 0.
4. [todo] In `examples/DOX.md`, change the bullet text `pinned third-party images (`haproxy:3.2`, `alpine:3.22`) where a version matters` to `pinned third-party images (`haproxy:3.2`, `alpine:3.22`, `traefik/whoami:v1.12.0`, `curlimages/curl:8.23.0`); never `:latest`` — done when: `grep -c 'never `:latest`' examples/DOX.md` prints `1`.

## Verify
```sh
bash -n examples/smoke-test.sh
test -z "$(grep -rn ':latest' examples --include='compose*.yaml')"
grep -c 'Six runnable Compose projects' README.md
for d in examples/*/; do (cd "$d" && docker compose config -q) || exit 1; done
git diff --exit-code -- site docs
```
- manual (planner, needs Docker running): `examples/smoke-test.sh ssh-tunnel homelab-stack direct egress-sandbox` passes.

## Escalate when
- `docker compose config -q` fails in an example → stop, set Status: needs-human — reason: paste the error.
- The `homelab-stack)` block no longer contains `wait_pool tunnel_pool 2` → stop, set Status: needs-human — reason: paste the block.

## Log
- (append-only, one line per event)

## Evidence
- (append-only: command → observed result)
