#!/usr/bin/env python3
"""Keep every skill-local operating-contract.md identical to the canonical copy.

Skills must stay self-contained when packaged independently, so each skill
that relies on the shared operating contract keeps its own copy of
references/operating-contract.md. This script copies the canonical file
(references/operating-contract.md) into every skill-local copy so the copies
can never silently drift.

Usage:
    python3 scripts/sync_operating_contract.py            # copy canonical -> copies
    python3 scripts/sync_operating_contract.py --check    # fail on any drift

Exit codes:
    0  copies are synchronized (or were synchronized)
    1  drift detected (--check)
    2  usage or IO error
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COPY_NAME = "operating-contract.md"


def skill_copies() -> list[Path]:
    """Every skill-local operating-contract.md, sorted."""
    skills_dir = REPO_ROOT / "skills"
    canonical = REPO_ROOT / "references" / COPY_NAME
    if not skills_dir.is_dir():
        return []
    return sorted(skills_dir.glob(f"*/references/{COPY_NAME}"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sync(check_only: bool) -> int:
    canonical = REPO_ROOT / "references" / COPY_NAME
    if not canonical.is_file():
        print(f"canonical operating contract missing: {canonical}", file=sys.stderr)
        return 2

    canonical_digest = digest(canonical)
    drifted: list[Path] = []

    for copy in skill_copies():
        if digest(copy) != canonical_digest:
            drifted.append(copy)

    if check_only:
        if drifted:
            for copy in drifted:
                print(f"[DRIFT] {copy.relative_to(REPO_ROOT)}")
            print(f"FAIL: {len(drifted)} skill-local copy/copies differ from {canonical.relative_to(REPO_ROOT)}")
            return 1
        print(f"OK: all {len(skill_copies())} skill-local operating-contract copies match the canonical file")
        return 0

    for copy in drifted:
        shutil.copyfile(canonical, copy)
        print(f"synced {copy.relative_to(REPO_ROOT)}")
    print(f"OK: {len(drifted)} copy/copies synced; {len(skill_copies()) - len(drifted)} already current")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync skill-local operating-contract copies.")
    parser.add_argument("--check", action="store_true", help="fail on any drift; do not write")
    args = parser.parse_args()
    return sync(args.check)


if __name__ == "__main__":
    sys.exit(main())
