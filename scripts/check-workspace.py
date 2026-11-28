#!/usr/bin/env python3
"""Check workspace consistency: engine pins, generated site diagrams, and Markdown links.

Usage: python3 scripts/check-workspace.py

1. Engine pin: the four consumers pin the same rusty-conduit-engine tag, and the GUI
   docs and workflows name that tag. Skipped when the member repos are not cloned.
2. Site diagrams: site/img/ matches the output of scripts/site-diagrams.py.
3. Markdown links: relative links in README.md, docs/*.md and examples/**/*.md resolve.

Prints one line per check and exits 0 only when no check failed.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONSUMERS = ("rusty-conduit", "rusty-conduit-ssh", "rusty-conduit-switch", "rusty-conduit-gui")
GUI_DOCS = (
    "rusty-conduit-gui/README.md",
    "rusty-conduit-gui/docs/RELEASING.md",
    "rusty-conduit-gui/.github/workflows/ci.yml",
    "rusty-conduit-gui/.github/workflows/release.yml",
)
PIN = re.compile(r'rusty-conduit-engine\s*=\s*\{[^}]*\btag\s*=\s*"(v\d+\.\d+\.\d+)"')
DOC_TAG = re.compile(r"rusty-conduit-engine.*?\b(v\d+\.\d+\.\d+)\b")
LINK = re.compile(r"\]\(([^)\s]+)\)")
SCHEME = re.compile(r"^[a-z]+:")


def fail(lines):
    for line in lines:
        print(line, file=sys.stderr)
    return False


def check_engine_pin():
    manifests = [ROOT / name / "Cargo.toml" for name in CONSUMERS]
    if not all(path.is_file() for path in manifests):
        print("SKIP engine pin: member repos not cloned (run scripts/bootstrap.sh)")
        return True
    tags = {}
    errors = []
    for path in manifests:
        rel = path.relative_to(ROOT).as_posix()
        match = PIN.search(path.read_text(encoding="utf-8"))
        if match:
            tags[rel] = match.group(1)
        else:
            errors.append(f"{rel}: no rusty-conduit-engine tag pin found")
    if errors:
        return fail(["FAIL engine pin"] + errors)
    expected = tags[f"{CONSUMERS[0]}/Cargo.toml"]
    if len(set(tags.values())) > 1:
        counts = {tag: list(tags.values()).count(tag) for tag in tags.values()}
        expected = max(counts, key=lambda tag: (counts[tag], tag == expected))
        for rel, tag in tags.items():
            if tag != expected:
                errors.append(f"{rel}: found {tag}, expected {expected}")
    doc_lines = 0
    for rel in GUI_DOCS:
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"{rel}: missing")
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = DOC_TAG.search(line)
            if not match:
                continue
            doc_lines += 1
            if match.group(1) != expected:
                errors.append(f"{rel}:{number}: found {match.group(1)}, expected {expected}")
    if errors:
        return fail(["FAIL engine pin"] + errors)
    print(f"OK engine pin {expected} ({len(CONSUMERS)} consumers, {doc_lines} doc lines)")
    return True


def check_site_diagrams():
    generate = subprocess.run(
        [sys.executable, "scripts/site-diagrams.py"], cwd=ROOT, capture_output=True, text=True
    )
    if generate.returncode != 0:
        return fail(["FAIL site diagrams: scripts/site-diagrams.py failed", generate.stderr.strip()])
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", "site/img"], cwd=ROOT, capture_output=True, text=True
    )
    if status.returncode != 0:
        return fail(["FAIL site diagrams: git status failed", status.stderr.strip()])
    if status.stdout.strip():
        return fail(
            ["FAIL site diagrams: rerun scripts/site-diagrams.py and commit site/img"]
            + status.stdout.rstrip().splitlines()
        )
    print("OK site diagrams")
    return True


def check_markdown_links():
    files = [ROOT / "README.md"] + sorted((ROOT / "docs").glob("*.md"))
    files += sorted((ROOT / "examples").glob("**/*.md"))
    errors = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        for target in LINK.findall(path.read_text(encoding="utf-8")):
            if SCHEME.match(target) or target.startswith("#"):
                continue
            local = target.split("#", 1)[0]
            if not (path.parent / local).exists():
                errors.append(f"{rel}: broken link {target}")
    if errors:
        return fail(["FAIL markdown links"] + errors)
    print(f"OK markdown links ({len(files)} files)")
    return True


def main():
    results = [check_engine_pin(), check_site_diagrams(), check_markdown_links()]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
