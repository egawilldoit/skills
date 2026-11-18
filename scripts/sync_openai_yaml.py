#!/usr/bin/env python3
"""Generate and check agents/openai.yaml for every skill.

The interface metadata is curated per skill: display_name, short_description,
and default_prompt are written by hand, not derived mechanically, because they
decide how the skill is presented and invoked.

Rules enforced (from the OpenAI skill-creator openai.yaml reference):
  * keys unquoted, all string values double quoted
  * short_description is 25-64 characters
  * default_prompt names the skill as $skill-name

Usage:
    python3 scripts/sync_openai_yaml.py            # write files
    python3 scripts/sync_openai_yaml.py --check     # verify files are current
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"

# name -> (display_name, short_description, default_prompt)
#
# The active catalog is empty. Add an entry when adding a skill, then run
# `python3 scripts/sync_openai_yaml.py` to generate agents/openai.yaml. The
# --check gate still fails if a catalog skill has no curated entry or if
# generated metadata is stale; an empty table with an empty catalog is valid.
METADATA: dict[str, tuple[str, str, str]] = {}

MIN_SHORT = 25
MAX_SHORT = 64


def render(name: str, display_name: str, short: str, prompt: str) -> str:
    return (
        "interface:\n"
        f'  display_name: "{display_name}"\n'
        f'  short_description: "{short}"\n'
        f'  default_prompt: "{prompt}"\n'
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    skill_names = sorted(p.name for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file())
    problems: list[str] = []

    missing = sorted(set(skill_names) - set(METADATA))
    extra = sorted(set(METADATA) - set(skill_names))
    for name in missing:
        problems.append(f"{name}: no curated interface metadata")
    for name in extra:
        problems.append(f"{name}: metadata exists but no skill directory")

    stale: list[str] = []
    for name in skill_names:
        if name not in METADATA:
            continue
        display_name, short, prompt = METADATA[name]
        if not (MIN_SHORT <= len(short) <= MAX_SHORT):
            problems.append(f"{name}: short_description length {len(short)} outside {MIN_SHORT}-{MAX_SHORT}")
        if f"${name}" not in prompt:
            problems.append(f"{name}: default_prompt does not mention ${name}")

        target = SKILLS_DIR / name / "agents" / "openai.yaml"
        content = render(name, display_name, short, prompt)
        if args.check:
            if not target.is_file() or target.read_text() != content:
                stale.append(name)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)

    for problem in problems:
        print(f"[ERROR] {problem}")
    if args.check:
        for name in stale:
            print(f"[ERROR] {name}: agents/openai.yaml is missing or out of date")
        if problems or stale:
            return 1
        print(f"[OK] {len(skill_names)} skills have current agents/openai.yaml")
        return 0
    if problems:
        return 1
    print(f"[OK] wrote agents/openai.yaml for {len(skill_names)} skills")
    return 0


if __name__ == "__main__":
    sys.exit(main())
