#!/usr/bin/env bash
# Clone the member repositories listed in repos.tsv into this workspace.
#
# Usage: scripts/bootstrap.sh [--pull] [--check]
#   (no flag)  clone every missing repo; report the state of the others
#   --pull     also fast-forward each clean repo that is on its listed branch
#   --check    clone nothing; exit 1 if any repo is missing or misconfigured
#
# Environment:
#   RCS_REMOTE_PREFIX  remote URL prefix (default: git@github.com:)
#                      e.g. https://github.com/ for token-based HTTPS clones
#
# Safe to re-run. It never touches a repo with uncommitted changes, never
# switches branches, and never changes an existing remote.
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
manifest="$root/repos.tsv"
prefix=${RCS_REMOTE_PREFIX:-git@github.com:}
pull=0 check=0

for arg in "$@"; do
  case $arg in
    --pull) pull=1 ;;
    --check) check=1 ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "bootstrap: unknown option: $arg" >&2; exit 2 ;;
  esac
done

[ -f "$manifest" ] || { echo "bootstrap: missing $manifest" >&2; exit 2; }

problems=0
while IFS=$'\t' read -r folder slug branch; do
  case $folder in ''|'#'*) continue ;; esac
  dir="$root/$folder"
  url="$prefix$slug.git"

  if [ ! -e "$dir" ]; then
    if [ "$check" -eq 1 ]; then
      echo "MISSING  $folder"
      problems=$((problems + 1))
      continue
    fi
    echo "CLONE    $folder  <- $url ($branch)"
    git clone --quiet --branch "$branch" "$url" "$dir"
    continue
  fi

  if [ ! -d "$dir/.git" ]; then
    echo "PROBLEM  $folder exists but is not a git repository"
    problems=$((problems + 1))
    continue
  fi

  current=$(git -C "$dir" branch --show-current)
  origin=$(git -C "$dir" remote get-url origin 2>/dev/null || echo "(none)")
  dirty=$(git -C "$dir" status --porcelain | wc -l | tr -d ' ')
  note=""

  case $origin in
    *"$slug"|*"$slug.git") ;;
    *) note="$note; origin is $origin, expected $slug"; problems=$((problems + 1)) ;;
  esac
  [ "$current" = "$branch" ] || note="$note; on '${current:-detached HEAD}', listed branch is $branch"
  [ "$dirty" -eq 0 ] || note="$note; $dirty uncommitted change(s)"

  if [ "$pull" -eq 1 ] && [ "$check" -eq 0 ]; then
    if [ "$dirty" -eq 0 ] && [ "$current" = "$branch" ]; then
      git -C "$dir" pull --quiet --ff-only && note="$note; pulled"
    else
      note="$note; not pulled"
    fi
  fi

  echo "OK       $folder (${current:-detached})${note}"
done < "$manifest"

if [ "$problems" -gt 0 ]; then
  echo "bootstrap: $problems problem(s) found" >&2
  exit 1
fi
