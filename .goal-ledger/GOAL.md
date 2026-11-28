# GOAL — Optimization roadmap Phase 1 for the rusty-conduit-series workspace

## Goal
- Goal ID: 20261128-optimization-phase1
- Outcome: The workspace README counts six examples, third-party example images are pinned, the homelab smoke test waits for every pool it checks, example host ports can be overridden by environment variables so the smoke test can run beside a local proxy, and `scripts/check-workspace.py` (run in CI) checks engine-pin consistency, generated-diagram freshness, and relative Markdown links.
- Done when: `bash -n examples/smoke-test.sh && bash -n scripts/bootstrap.sh && python3 scripts/check-workspace.py && scripts/bootstrap.sh --check` exits 0, `docker compose config -q` passes in every example, and (with Docker running) `examples/smoke-test.sh` passes for every example.
- Goal status: approved
- Goal status meaning: drafting | approved | executing | blocked-on-human | in-review | awaiting-acceptance | completed | abandoned
- Last completed phase: none

## Execution
- Execution mode: delegated
- Planner tier: Claude Code (claude-opus-5-5)
- Executor tier: agy --model gemini-4-neon-medium via the herdr-subagent skill
- Full verification: bash -n examples/smoke-test.sh && bash -n scripts/bootstrap.sh && python3 scripts/check-workspace.py && scripts/bootstrap.sh --check && for d in examples/*/; do (cd "$d" && docker compose config -q) || exit 1; done

## Git
- Repository: yes
- Strategy: isolated-branch
- Starting branch: main
- Work branch: goal/20261128-optimization-phase1
- Baseline commit: ff0f723b4e431315951c8f09fafbe20cff3a0a94
- Starting upstream at start: origin/main@ba76419abe498833f20e8e0eec5cb7052bfadd8a
- Work upstream at start: none

## Phases
- [todo] phase-0001 — README example count, pinned example images, homelab pool waits
- [todo] phase-0002 — Overridable example host ports
- [todo] phase-0003 — Workspace consistency check script and CI workflow

## Handoff
- Current position: approved; branch prepared, execution not started
- Next role: planner
- Next action: Gate C — wait for the user to start execution, then begin phase-0001
- Last verified evidence: none
- Blockers: none

## Review
- Reviewed by: none
- Verification result: none
- Diff reviewed: none
- Findings: none

## Log
- created ledger with 3 phases (first ledger in this repo)
- source plan: docs/OPTIMIZATION.md, roadmap Phase 1 (items B-12, M-06)
- sibling ledgers with the same Goal ID: rusty-conduit, rusty-conduit-switch, rusty-conduit-ssh, rusty-conduit-gui (each in its own repo; this ledger covers only workspace-owned files)
- user decisions: roadmap Phase 1 only; delegated to agy neon medium via herdr; pre-existing DOX.md/examples/DOX.md edits and docs/OPTIMIZATION.md committed first as ff0f723
- planner decisions: `wait_pool` keeps returning 0 on timeout (by design: the `expect` after it reports the failure, while a non-zero return would abort the run under `set -e` before the other checks); image pins `traefik/whoami:v1.12.0` and `curlimages/curl:8.23.0` are the newest tags on Docker Hub as of 2026-11-28
- the example smoke test needs a running Docker daemon; it was not running when this plan was written
- user approved the goal (Gate A) on 2026-11-28
- Gate B: isolated branch goal/20261128-optimization-phase1 created from main at baseline ff0f723b4e431315951c8f09fafbe20cff3a0a94; user asked to commit only and not start execution yet
