# phase-0002 — Overridable example host ports

- Status: done
- Owner: executor
- Depends on: phase-0001
- Goal: Let every example's published host port be overridden with `RCS_PORT_<default port>` (for example `RCS_PORT_3128=13128`), and make the smoke test use the same variables, so it can run while a developer's own proxy holds 3128 or 1080.
- Done when: every command in `## Verify` exits 0.
- Pattern to follow: none (the naming rule below is the pattern)

## Context
The examples publish fixed host ports `127.0.0.1:3128`, `1080`, `8080`, and `8404`, and `examples/smoke-test.sh` curls those literals, so it collides with any proxy already running locally. The planner fixed the naming: the variable for default host port `N` is `RCS_PORT_N`. The container side of each mapping never changes, and with no variable set everything behaves exactly as before, so the docs' `127.0.0.1:3128` commands stay correct.
Mapping lines today (planner listed them): `direct` 3128, 1080; `switch` 3128, 1080; `ssh-tunnel` 3128, 1080, 8080; `scale-out` 3128, 1080, 8404; `homelab-stack` 3128, 1080, 8404. `egress-sandbox` publishes none.

## Scope
- In: `examples/*/compose.yaml` (the `ports:` entries only), `examples/smoke-test.sh`, `examples/README.md` (the ports sentence near line 25 only), `examples/DOX.md` (Verification bullet only)
- Out: `docs/`, `README.md`, `site/`, every config file under `examples/*/conf/`, `examples/*/haproxy.cfg`

## Sub-tasks
1. [done] In every `examples/*/compose.yaml`, rewrite each port entry of the form `"127.0.0.1:N:M"` to `"127.0.0.1:${RCS_PORT_N:-N}:M"`, keeping any trailing comment (example: `- "127.0.0.1:3128:3128"   # HTTP/HTTPS` becomes `- "127.0.0.1:${RCS_PORT_3128:-3128}:3128"   # HTTP/HTTPS`) — done when: `grep -rnE '"127\.0\.0\.1:[0-9]+:[0-9]+"' examples --include=compose.yaml` prints nothing and `grep -rc 'RCS_PORT_' examples --include=compose.yaml` totals 13.
2. [done] In `examples/smoke-test.sh`, after `set -euo pipefail`, add exactly: (block 1 below) Then replace every literal `127.0.0.1:3128`, `127.0.0.1:1080`, `127.0.0.1:8080`, and `127.0.0.1:8404` in the script with `127.0.0.1:$p3128`, `127.0.0.1:$p1080`, `127.0.0.1:$p8080`, `127.0.0.1:$p8404`. Leave `127.0.0.1:8888` (inside the `sshd` container) unchanged. In the header comment, change the line `# Uses host ports 127.0.0.1:1080, 3128, 8080, and 8404, so stop anything on them first.` to `# Uses host ports 127.0.0.1:1080, 3128, 8080, and 8404; set RCS_PORT_<port> to move any of them.` — done when: `grep -cE '127\.0\.0\.1:(3128|1080|8080|8404)' examples/smoke-test.sh` prints `1` (the header line) and `bash -n examples/smoke-test.sh` exits 0.
   Block 1:
   ```bash
   # Host ports; override any of them to run beside a proxy you already have (RCS_PORT_3128=13128 ...).
   p3128=${RCS_PORT_3128:-3128}
   p1080=${RCS_PORT_1080:-1080}
   p8080=${RCS_PORT_8080:-8080}
   p8404=${RCS_PORT_8404:-8404}
   export RCS_PORT_3128=$p3128 RCS_PORT_1080=$p1080 RCS_PORT_8080=$p8080 RCS_PORT_8404=$p8404
   ```
3. [done] In `examples/README.md`, after the sentence `The examples publish on `127.0.0.1` ports `3128`, `1080`, `8080`, and `8404`, so run one at a time.`, add: ` To move a port, set `RCS_PORT_<port>` (for example `RCS_PORT_3128=13128 docker compose up -d`); `smoke-test.sh` honours the same variables.` In `examples/DOX.md` Verification, change `uses host ports 1080, 3128, 8080, 8404` to `uses host ports 1080, 3128, 8080, 8404, each overridable with `RCS_PORT_<port>`` — done when: `grep -c 'RCS_PORT_' examples/README.md examples/DOX.md` shows at least 1 for each file.

## Verify
```sh
bash -n examples/smoke-test.sh
test -z "$(grep -rnE '"127\.0\.0\.1:[0-9]+:[0-9]+"' examples --include=compose.yaml)"
for f in examples/*/compose.yaml; do (cd "$(dirname "$f")" && docker compose config -q) || exit 1; done
(cd examples/direct && RCS_PORT_3128=13128 docker compose config | grep -q 'published: "13128"')
git diff --exit-code -- docs README.md site
```
- manual (planner, needs Docker running): `RCS_PORT_3128=13128 RCS_PORT_1080=11080 examples/smoke-test.sh direct` passes while something else listens on 3128.

## Escalate when
- A `ports:` entry does not match the `"127.0.0.1:N:M"` form → stop, set Status: needs-human — reason: paste the line.
- `docker compose config` prints the published port in a form other than `published: "13128"` → adjust only that grep to the printed form and record it in the Log (allowed fix-up); anything else failing → stop, set Status: needs-human — reason: paste the output.

## Log
- (append-only, one line per event)
- planner fixed Verify compose loop to iterate examples/*/compose.yaml (skipping examples/lab/) before delegating
- executor: sub-task 1 rewrote 13 port entries in 5 compose files to `"127.0.0.1:${RCS_PORT_N:-N}:M"`, comments kept
- executor: sub-task 2 added block 1 after `set -euo pipefail`, replaced host-port literals with `$pNNNN`, updated header; 127.0.0.1:8888 left as is. Also changed the quotes on the HAProxy stats URL (line 49) from single to double, because `$p8404` would not expand inside single quotes
- executor: sub-task 3 added the RCS_PORT_<port> sentence to examples/README.md:25 and the override note to the examples/DOX.md Verification bullet
- executor: ## Verify passed on first run (all 5 commands exit 0); manual smoke test left to the planner

## Evidence
- (append-only: command → observed result)
- sub-task 1: `grep -rnE '"127\.0\.0\.1:[0-9]+:[0-9]+"' examples --include=compose.yaml` → no output (rc=1); `grep -rc 'RCS_PORT_' examples --include=compose.yaml` → total 13
- sub-task 2: `grep -cE '127\.0\.0\.1:(3128|1080|8080|8404)' examples/smoke-test.sh` → 1; `bash -n examples/smoke-test.sh` → rc 0
- sub-task 3: `grep -c 'RCS_PORT_' examples/README.md examples/DOX.md` → examples/DOX.md:1, examples/README.md:1
- Verify (5 commands from ## Verify, run from project root, Docker running): bash -n → 0; no fixed compose port entries → 0; compose config -q loop over 6 examples → 0; `RCS_PORT_3128=13128 docker compose config | grep -q 'published: "13128"'` in examples/direct → 0; `git diff --exit-code -- docs README.md site` → 0
