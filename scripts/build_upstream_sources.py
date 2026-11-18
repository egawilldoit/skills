#!/usr/bin/env python3
"""Build upstream-sources.json from the pinned Cursor source.

Every imported or adapted skill records its source path, the single pinned
source commit, its license, and its import mode. Original skills record mode
only. Output is sorted deterministically.

Usage:
    python3 scripts/build_upstream_sources.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "upstream-sources.json"

SOURCE_REPOSITORY = "https://github.com/cursor/plugins"
SOURCE_COMMIT = "12d587dfb20741cafc376c42c696c5f6e2a64487"
LICENSE = "MIT"

PSTACK = "pstack/skills"
TEAM_KIT = "cursor-team-kit/skills"

# The active catalog is empty. Populate these tables only when adding a
# sourced skill, and keep them in sync with skills/. This generator must not
# repopulate provenance for skills that are not present in the catalog.
# Historical entries remain recoverable from Git history.
COPIED: dict[str, str] = {}

# new skill -> list of (upstream skill name, upstream path)
ADAPTED: dict[str, list[tuple[str, str]]] = {}

ORIGINAL: list[str] = []


def entry(skill: str) -> dict:
    if skill in COPIED:
        return {
            "skill": skill,
            "origin": "cursor/plugins",
            "source_path": COPIED[skill],
            "source_commit": SOURCE_COMMIT,
            "license": LICENSE,
            "mode": "copied",
        }
    if skill in ADAPTED:
        pairs = ADAPTED[skill]
        if len(pairs) == 1:
            source_skill, source_path = pairs[0]
            return {
                "skill": skill,
                "origin": "cursor/plugins",
                "source_skill": source_skill,
                "source_path": source_path,
                "source_commit": SOURCE_COMMIT,
                "license": LICENSE,
                "mode": "adapted",
            }
        return {
            "skill": skill,
            "origin": "cursor/plugins",
            "source_skills": [p[0] for p in pairs],
            "source_paths": [p[1] for p in pairs],
            "source_commit": SOURCE_COMMIT,
            "license": LICENSE,
            "mode": "adapted",
        }
    if skill in ORIGINAL:
        return {"skill": skill, "mode": "original"}
    raise KeyError(skill)


def main() -> int:
    skills = sorted(set(COPIED) | set(ADAPTED) | set(ORIGINAL))
    document = {
        "source_repository": SOURCE_REPOSITORY,
        "source_commit": SOURCE_COMMIT,
        "generated_by": "scripts/build_upstream_sources.py",
        "sources": [entry(skill) for skill in skills],
    }
    OUT.write_text(json.dumps(document, indent=2, sort_keys=False) + "\n")
    counts = {"copied": len(COPIED), "adapted": len(ADAPTED), "original": len(ORIGINAL)}
    print(f"[OK] wrote {OUT.name}: {counts}, total {len(skills)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
