# Contributing: the agent workspace

Besides the docs and examples, this repo is the agent workspace for the
rusty-conduit family. It holds the agent rules (`DOX.md`) and a bootstrap
script. The five product repos are cloned into it as independent git repos and
are not tracked here.

- Back to [README](../README.md)

| Folder | What it is |
| --- | --- |
| `rusty-conduit-engine/` | Shared proxy engine library. Every other repo depends on it. |
| `rusty-conduit/` | Direct HTTP/HTTPS/SOCKS proxy CLI. |
| `rusty-conduit-ssh/` | Proxy CLI that dials through an `ssh -D` tunnel. |
| `rusty-conduit-switch/` | Rule-based proxy switcher CLI. |
| `rusty-conduit-gui/` | Tauri desktop app. |

You don't need to remember the rules. Agents read `AGENTS.md`, which points
them to `DOX.md`, and that file holds the full contract. This page is the
short version for you: what to run, and what to say to an agent. The
user-facing docs in `docs/` and the runnable projects in `examples/` are
workspace files too; see [Changing the docs and examples](#changing-the-docs-and-examples).

## Setup

New machine or fresh clone:

```sh
git clone https://github.com/jpbaking/rusty-conduit-series.git
cd rusty-conduit-series
RCS_REMOTE_PREFIX=https://github.com/ scripts/bootstrap.sh   # or just scripts/bootstrap.sh with GitHub SSH keys
```

Start of a work session, to fast-forward every clean repo:

```sh
scripts/bootstrap.sh --pull
```

Check without changing anything (missing repos, wrong remote, branch,
uncommitted changes):

```sh
scripts/bootstrap.sh --check
```

The script is safe to re-run. It never touches a repo with uncommitted changes,
never switches branches, and never changes a remote.

## Working with agents

Start the agent (Claude Code, agy, Codex, Gemini CLI, Cline or OpenCode) **in
this folder** for anything that spans repos, or inside one repo for work that
stays there. Either way it loads the right rules on its own.

Things agents already know from `DOX.md`, so you don't need to say them:

- run bootstrap if a repo is missing;
- commit each change in the repo that owns the file, never in this workspace;
- commit, push or tag only when you ask;
- follow each repo's own rules and verification commands;
- the engine release order and the version-pin rules.

### Prompts to copy

**Change one repo**

> In rusty-conduit-switch, add <feature>. Run its verification. Don't commit yet.

**Change that spans repos**

> Add <feature> to the engine and use it in rusty-conduit-ssh and rusty-conduit-gui. Follow the workspace DOX rules for cross-repo work.

**Release the engine and update the consumers**

> Release rusty-conduit-engine as vX.Y.Z following the engine release order in DOX.md, with the release notes in the tag message, then bump every consumer to that tag and update any docs that name the engine version. Stop before tagging and pushing so I can review.

**Test consumers against an unreleased engine**

> Build and test rusty-conduit-switch against my local rusty-conduit-engine using the `[patch]` override described in DOX.md. Don't commit the override or the lockfile.

**Commit and push when you're happy**

> Commit and push all repos that have changes.

**Work with several phases, or that may span sessions**

> Use the goal-ledger skill to plan <goal> in this workspace.

**Run the work in visible herdr panes**

> Do <task> using the herdr-subagent skill with <agent and model>.

### Keeping the docs healthy

| When | Say |
| --- | --- |
| Now and then, or before a release | "Use the dox-audit skill on every repo in this workspace." |
| Audit found problems | "Use the dox-fix skill on <repo>." |
| After a big refactor | "Use the dox-remap skill on <repo>." |
| A new folder deserves its own doc | "Use the dox-child skill on <repo>/<folder>." |

Agents update the docs as part of normal work. These skills are for cleanup.

## Cloning over SSH or HTTPS

Bootstrap clones over SSH (`git@github.com:`) by default. Every member repo is
public, so without GitHub SSH keys (cloud or sandboxed agents, a first look),
clone over HTTPS instead; pushing still needs your own credentials:

```sh
RCS_REMOTE_PREFIX=https://github.com/ scripts/bootstrap.sh
```

The prefix applies only to new clones. Existing remotes are never changed.

## Changing the docs and examples

`README.md`, `docs/`, and `examples/` are committed in this workspace repo, not
in a member repo. They describe what the released products do, so:

- Check a claim against the owning repo's own guide or code before writing it,
  and link to that guide rather than copying its reference tables.
- After changing an example, run `examples/smoke-test.sh <example>` (it needs
  Docker and internet access). Its rules are in `examples/DOX.md`.
- When a product release changes a flag, a default, or an image tag that these
  docs use, update them in the same pass.

> Update the docs in this workspace for <change>, and run the smoke test for any example you touch.

## Adding or removing a repo

> Add <owner/name> to this workspace as a member repo.

The agent updates `repos.tsv`, `.gitignore`, `.ignore` and the Child DOX Index
in `DOX.md` together. To do it by hand, change all four. If the new repo is a
product, add it to the tool table in `README.md` too.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `examples/smoke-test.sh` fails with `Bind for 127.0.0.1:3128 failed` | Another proxy or example is using the port. Stop it (`docker compose down` in that example) and run the test again. |
| An agent's search finds nothing in the repos | `.ignore` is missing or out of date. It re-includes the gitignored repos for search tools. |
| `bootstrap.sh` reports `origin is ..., expected ...` | The repo was renamed or cloned from elsewhere. Run `git -C <repo> remote set-url origin <url>`. |
| `not pulled` | The repo has uncommitted changes or is on another branch. Commit, stash or switch, then run `--pull` again. |
| An agent refuses to edit the engine and a consumer together | The engine's own `DOX.md` limits edits to that repo. Tell the agent the task comes from this workspace, or update that rule in the engine repo. |
