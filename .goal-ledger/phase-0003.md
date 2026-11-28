# phase-0003 — Workspace consistency check script and CI workflow

- Status: done
- Owner: executor
- Depends on: phase-0002
- Goal: Add `scripts/check-workspace.py`, which fails when the consumers pin different engine tags, when the generated site diagrams are stale, or when a relative Markdown link is broken, and run it in CI on every push and pull request to `main`.
- Done when: every command in `## Verify` exits 0.
- Pattern to follow: `rusty-conduit-engine/scripts/check-pure-rust-crypto.py` (stdlib-only Python, `ROOT` from `__file__`, `main()` returning an exit code, one-line `OK` on success, details on stderr on failure)

## Context
M-06: nothing checks that all four consumers pin the same `rusty-conduit-engine` tag, that the GUI docs and workflows name that tag, that `site/img/` matches `scripts/site-diagrams.py`, or that relative links in the public docs resolve. The member repos are gitignored here, so in CI (where only the workspace is checked out) the pin checks must print a `SKIP` line instead of failing. The planner prototyped the link check: the 9 Markdown files it covers have no broken links today, and `python3 scripts/site-diagrams.py` leaves no diff today.
The workspace DOX lists the files this repo tracks, its Feature Map, and its Verification; a new script and workflow must be added to all three, and `docs/WORKSPACE.md` (the human guide to the workspace contract) gets one sentence.

## Scope
- In: `scripts/check-workspace.py` (new), `.github/workflows/check.yml` (new), `DOX.md` (Workspace Contract tracked-files sentence, Feature Map, Verification), `docs/WORKSPACE.md` (one sentence)
- Out: `scripts/site-diagrams.py`, `site/`, `.github/workflows/pages.yml`, member repos, every other doc

## Sub-tasks
1. [done] Write `scripts/check-workspace.py` (stdlib only, executable, `#!/usr/bin/env python3`, module docstring) with three checks run in order, each printing one line: - **Engine pin.** If any of `rusty-conduit/Cargo.toml`, `rusty-conduit-ssh/Cargo.toml`, `rusty-conduit-switch/Cargo.toml`, `rusty-conduit-gui/Cargo.toml` is missing, print `SKIP engine pin: member repos not cloned (run scripts/bootstrap.sh)` and continue. Otherwise read the tag from the `rusty-conduit-engine = { ... tag = "vX.Y.Z" ... }` line of each (regex `rusty-conduit-engine\s*=\s*\{[^}]*\btag\s*=\s*"(v\d+\.\d+\.\d+)"`); all four must be equal. Then, in `rusty-conduit-gui/README.md`, `rusty-conduit-gui/docs/RELEASING.md`, `rusty-conduit-gui/.github/workflows/ci.yml`, and `rusty-conduit-gui/.github/workflows/release.yml`, every line matching `rusty-conduit-engine.*?\b(v\d+\.\d+\.\d+)\b` must name that same tag. Print `OK engine pin vX.Y.Z (4 consumers, N doc lines)` or, on failure, every mismatch as `path:line: found vA.B.C, expected vX.Y.Z`. - **Site diagrams.** Run `python3 scripts/site-diagrams.py` from the root, then `git status --porcelain -- site/img`; any output is a failure listing those paths with the hint `rerun scripts/site-diagrams.py and commit site/img`. Print `OK site diagrams`. - **Markdown links.** In `README.md`, `docs/*.md`, and `examples/**/*.md`, every `](target)` whose target has no URL scheme (`^[a-z]+:`) and does not start with `#` must resolve, after dropping any `#fragment`, to an existing path relative to the file's folder. Print `OK markdown links (N files)` or each failure as `path: broken link target`. Exit 0 only when no check failed — done when: `python3 scripts/check-workspace.py` exits 0 and prints three `OK` lines.
2. [done] Prove each check can fail, without committing the breakage: (a) `sed -i.bak 's/tag = "v0.6.0"/tag = "v0.0.1"/' rusty-conduit/Cargo.toml`, run the script, expect exit 1 naming `rusty-conduit/Cargo.toml`, then `mv rusty-conduit/Cargo.toml.bak rusty-conduit/Cargo.toml`; (b) append `[x](missing.md)` to a copy: `cp README.md /tmp/rcs-readme.bak && echo '[x](missing.md)' >> README.md`, expect exit 1 naming `missing.md`, then `mv /tmp/rcs-readme.bak README.md` — done when: both runs exited 1, and afterwards `git -C rusty-conduit status --porcelain` and `git status --porcelain -- README.md` print nothing (record all four outputs in Evidence).
3. [done] Add `.github/workflows/check.yml`: name `Check`; on `push` and `pull_request` to `main`; one job `check` on `ubuntu-latest` with `permissions: contents: read`, steps `actions/checkout@v7` (the version `pages.yml` uses) and `- run: python3 scripts/check-workspace.py` — done when: `ruby -ryaml -e 'YAML.load_file(".github/workflows/check.yml")'` exits 0.
4. [done] DOX and guide pass: in `DOX.md` Workspace Contract, add `.github/workflows/check.yml` to the list of tracked files next to `.github/workflows/pages.yml`; add the Feature Map bullet `- **Workspace consistency check** — engine-pin agreement across consumers and GUI docs, generated-diagram freshness, and relative Markdown links; runs in CI. Start: `scripts/check-workspace.py`. Files: `.github/workflows/check.yml`.`; add the Verification bullet `- `python3 scripts/check-workspace.py` exits 0 (run after `scripts/bootstrap.sh` so the engine-pin check is not skipped).`. In `docs/WORKSPACE.md`, near the bootstrap commands, add one sentence: `Run `python3 scripts/check-workspace.py` to check that every consumer pins the same engine tag, the site diagrams are current, and the docs' relative links resolve.` — done when: `grep -c 'check-workspace.py' DOX.md` prints at least `2` and `grep -c 'check-workspace.py' docs/WORKSPACE.md` prints at least `1`.

## Verify
```sh
python3 scripts/check-workspace.py
test -x scripts/check-workspace.py
ruby -ryaml -e 'YAML.load_file(".github/workflows/check.yml")'
test -z "$(git -C rusty-conduit status --porcelain)"
git diff --exit-code -- scripts/site-diagrams.py site .github/workflows/pages.yml README.md
python3 scripts/site-diagrams.py && test -z "$(git status --porcelain -- site/img)"
```

## Escalate when
- The link or diagram check fails on the unmodified tree → stop, set Status: needs-human — reason: paste the failures (fixing docs is out of scope).
- A GUI doc line names the engine with a version that is not the pin and is not meant to be (for example release history) → stop, set Status: needs-human — reason: paste the line.
- `git -C rusty-conduit status --porcelain` is not empty before sub-task 2 (someone else's work in that repo) → do not touch it; stop, set Status: needs-human — reason: rusty-conduit is dirty.
- Restoring a file in sub-task 2 fails → stop immediately, set Status: needs-human — reason: name the file left modified.

## Log
- (append-only, one line per event)
- executor (claude opus): began phase-0003; rusty-conduit clean before sub-task 2
- sub-task 1: wrote scripts/check-workspace.py (stdlib, executable, three checks); on mismatched pins the expected tag is the majority tag, ties broken toward rusty-conduit's pin; a GUI doc line is checked by its first version after `rusty-conduit-engine` (README.md:10 also names rusty-conduit-ssh-gui v0.1.0 later on the line, which is not checked)
- sub-task 2: broke the rusty-conduit pin and a README link in turn; both runs exited 1; both files restored
- sub-task 3: added .github/workflows/check.yml (push and pull_request to main, contents: read, actions/checkout@v7)
- sub-task 4: DOX.md tracked files, Verification and Feature Map entries added; one sentence added to docs/WORKSPACE.md after the bootstrap commands (line-wrapped to match the file)
- Verify: all six commands passed

## Evidence
- (append-only: command → observed result)
- `python3 scripts/check-workspace.py` → `OK engine pin v0.6.0 (4 consumers, 5 doc lines)` / `OK site diagrams` / `OK markdown links (9 files)`, exit 0
- `git -C rusty-conduit status --porcelain` before sub-task 2 → empty
- (2a) sed v0.6.0→v0.0.1 in rusty-conduit/Cargo.toml, run → stderr `FAIL engine pin` / `rusty-conduit/Cargo.toml: found v0.0.1, expected v0.6.0`, exit=1; restored with mv
- (2b) append `[x](missing.md)` to README.md, run → stderr `FAIL markdown links` / `README.md: broken link missing.md`, exit=1; restored with mv
- `git -C rusty-conduit status --porcelain` after → empty; `git status --porcelain -- README.md` after → empty
- `ruby -ryaml -e 'YAML.load_file(".github/workflows/check.yml")'` → exit 0
- `grep -c 'check-workspace.py' DOX.md` → 2; `grep -c 'check-workspace.py' docs/WORKSPACE.md` → 1
- Verify block (all six commands, under `set -e`) → all passed; `git status --porcelain` afterwards showed only DOX.md, docs/WORKSPACE.md, .github/workflows/check.yml, scripts/check-workspace.py
