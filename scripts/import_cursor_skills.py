#!/usr/bin/env python3
"""Import copy-mode skills from the pinned cursor/plugins source.

For each copy-mode skill this script:
  * reads the upstream SKILL.md,
  * drops Cursor-only frontmatter (e.g. disable-model-invocation),
  * keeps name + description and remaps cross-skill references to the
    skill names used in this catalog,
  * copies supporting files (references/, scripts/, assets/) verbatim,
  * writes our SKILL.md.

Copy-mode means the upstream methodology is preserved. The only body edits
are packaging normalization: frontmatter, and cross-skill references that
would otherwise be dead links because the referenced skill was renamed.

Usage:
    python3 scripts/import_cursor_skills.py --source /path/to/cursor-plugins
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"

PSTACK = "pstack/skills"
TEAM_KIT = "cursor-team-kit/skills"

# Cross-skill reference remapping. Keys are upstream skill names that appear
# backticked in copied bodies; values are the catalog skill that replaced them.
REFERENCE_MAP = {
    "how": "understand-codebase",
    "why": "recover-design-rationale",
    "architect": "design-architecture",
    "arena": "compare-designs",
    "interrogate": "adversarial-review",
    "recall": "recover-work-context",
    "reflect": "work-retrospective",
    "automate-me": "mine-work-patterns",
    "workflow-from-chats": "mine-work-patterns",
    "show-me-your-work": "record-evidence",
    "create-verification-skill": "create-verification-workflow",
    "maintain-verification-skill": "maintain-verification-workflow",
    "swarm": "parallelize-work",
    "figure-it-out": "design-investigation",
    "poteto-mode": "deliver-software",
    "control-ui": "verify-ui",
    "control-cli": "verify-cli",
}

# skill name -> source path (relative to the source repo root)
COPY_SKILLS = {
    # pstack
    "blast-radius": f"{PSTACK}/blast-radius",
    "tdd": f"{PSTACK}/tdd",
    "technical-writing": f"{PSTACK}/technical-writing",
    "typescript-best-practices": f"{PSTACK}/typescript-best-practices",
    "unslop": f"{PSTACK}/unslop",
    "principle-attack-the-premise": f"{PSTACK}/principle-attack-the-premise",
    "principle-boundary-discipline": f"{PSTACK}/principle-boundary-discipline",
    "principle-build-the-lever": f"{PSTACK}/principle-build-the-lever",
    "principle-encode-lessons-in-structure": f"{PSTACK}/principle-encode-lessons-in-structure",
    "principle-exhaust-the-design-space": f"{PSTACK}/principle-exhaust-the-design-space",
    "principle-experience-first": f"{PSTACK}/principle-experience-first",
    "principle-fix-root-causes": f"{PSTACK}/principle-fix-root-causes",
    "principle-foundational-thinking": f"{PSTACK}/principle-foundational-thinking",
    "principle-guard-the-context-window": f"{PSTACK}/principle-guard-the-context-window",
    "principle-laziness-protocol": f"{PSTACK}/principle-laziness-protocol",
    "principle-make-operations-idempotent": f"{PSTACK}/principle-make-operations-idempotent",
    "principle-migrate-callers-then-delete-legacy-apis": f"{PSTACK}/principle-migrate-callers-then-delete-legacy-apis",
    "principle-minimize-reader-load": f"{PSTACK}/principle-minimize-reader-load",
    "principle-model-the-domain": f"{PSTACK}/principle-model-the-domain",
    "principle-outcome-oriented-execution": f"{PSTACK}/principle-outcome-oriented-execution",
    "principle-prove-it-works": f"{PSTACK}/principle-prove-it-works",
    "principle-redesign-from-first-principles": f"{PSTACK}/principle-redesign-from-first-principles",
    "principle-separate-before-serializing-shared-state": f"{PSTACK}/principle-separate-before-serializing-shared-state",
    "principle-sequence-verifiable-units": f"{PSTACK}/principle-sequence-verifiable-units",
    "principle-subtract-before-you-add": f"{PSTACK}/principle-subtract-before-you-add",
    "principle-test-behavior-not-implementation": f"{PSTACK}/principle-test-behavior-not-implementation",
    "principle-type-system-discipline": f"{PSTACK}/principle-type-system-discipline",
    # cursor-team-kit
    "verify-this": f"{TEAM_KIT}/verify-this",
    "review-and-ship": f"{TEAM_KIT}/review-and-ship",
    "make-pr-easy-to-review": f"{TEAM_KIT}/make-pr-easy-to-review",
    "loop-on-ci": f"{TEAM_KIT}/loop-on-ci",
    "fix-ci": f"{TEAM_KIT}/fix-ci",
    "run-smoke-tests": f"{TEAM_KIT}/run-smoke-tests",
    "check-compiler-errors": f"{TEAM_KIT}/check-compiler-errors",
    "get-pr-comments": f"{TEAM_KIT}/get-pr-comments",
    "fix-merge-conflicts": f"{TEAM_KIT}/fix-merge-conflicts",
    "new-branch-and-pr": f"{TEAM_KIT}/new-branch-and-pr",
    "what-did-i-get-done": f"{TEAM_KIT}/what-did-i-get-done",
    "weekly-review": f"{TEAM_KIT}/weekly-review",
    "deslop": f"{TEAM_KIT}/deslop",
}

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("no YAML frontmatter found")
    import yaml

    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict):
        raise ValueError("frontmatter is not a mapping")
    return data, text[match.end():]


def remap_references(text: str) -> tuple[str, list[str]]:
    changed: list[str] = []
    for old, new in REFERENCE_MAP.items():
        pattern = re.compile(r"`" + re.escape(old) + r"`")
        if pattern.search(text):
            text = pattern.sub(f"`{new}`", text)
            changed.append(old)
    return text, changed


def quote_description(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def import_skill(name: str, src_rel: str, source_root: Path) -> dict:
    src = source_root / src_rel
    if not src.is_dir():
        raise FileNotFoundError(f"missing source skill dir: {src}")

    frontmatter, body = parse_frontmatter((src / "SKILL.md").read_text())
    description = str(frontmatter["description"]).strip()
    body, remapped = remap_references(body)
    description, desc_remapped = remap_references(description)
    remapped = sorted(set(remapped) | set(desc_remapped))

    dest = SKILLS_DIR / name
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    (dest / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        f"description: {quote_description(description)}\n"
        "---\n"
        f"{body}"
    )

    copied: list[str] = []
    for folder in ("references", "scripts", "assets"):
        src_folder = src / folder
        if src_folder.is_dir():
            shutil.copytree(src_folder, dest / folder)
            copied.extend(
                str(p.relative_to(src)).replace("\\", "/")
                for p in sorted(src_folder.rglob("*"))
                if p.is_file()
            )

    return {
        "skill": name,
        "origin": "cursor/plugins",
        "source_path": src_rel,
        "copied_files": copied,
        "remapped_references": remapped,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="path to cursor/plugins checkout")
    parser.add_argument("--report", help="optional path to write a JSON report")
    args = parser.parse_args()

    source_root = Path(args.source).resolve()
    if not (source_root / PSTACK).is_dir():
        raise SystemExit(f"not a cursor/plugins checkout: {source_root}")

    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    report = [import_skill(name, rel, source_root) for name, rel in COPY_SKILLS.items()]
    print(f"imported {len(report)} copy-mode skills")
    for row in report:
        note = f" remapped={','.join(row['remapped_references'])}" if row["remapped_references"] else ""
        extra = f" files={len(row['copied_files'])}" if row["copied_files"] else ""
        print(f"  - {row['skill']}{extra}{note}")

    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
