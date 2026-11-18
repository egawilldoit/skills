#!/usr/bin/env python3
"""Routing audit for the full catalog, using the trigger-case suite.

Two layers:

Structural (hard): the suite must cover every skill, every case must be
complete, and every referenced sibling must exist.

Lexical (soft): real activation is semantic, so the word-overlap check below is
only a signal, not a gate. It flags a case whose words sit much closer to a
declared sibling than to the intended skill. Descriptions that name their
neighbors on purpose create overlap, so a small number of informational flags
is expected. Investigate a flag; do not treat it as proof of a routing bug.

An empty catalog with an empty trigger-cases.json is valid. Structural checks
still fail if a case names an unknown skill, omits a required field, or if a
catalog skill has no case.

`negative_expected` and `collision_expected` may be a JSON null. That is the
explicit "no competing skill exists" sentinel used by the first skill. With
null, the negative/collision example must still contain at least three content
words and must not describe the target skill itself. A named neighbor must be
a catalog skill; null stays valid when later skills are added.

Usage:
    python3 scripts/trigger_audit.py [--margin 0.20]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
CASES = REPO_ROOT / "tests" / "trigger-cases.json"
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)

STOPWORDS = {
    "a", "an", "the", "and", "or", "to", "of", "for", "in", "on", "at", "by",
    "with", "is", "are", "be", "it", "its", "this", "that", "these", "those",
    "as", "when", "use", "used", "using", "into", "from", "before", "after",
    "not", "but", "if", "so", "than", "then", "them", "they", "their", "there",
    "you", "your", "we", "our", "i", "do", "does", "done", "can", "will",
    "skill", "skills", "one", "two", "all", "any", "each", "more", "most",
    "want", "still", "just", "about", "has", "have", "was", "were", "am",
}

TEXT_FIELDS = ("direct", "indirect", "incomplete", "negative", "collision", "edge")
NEIGHBOR_FIELDS = ("negative_expected", "collision_expected")
POSITIVE_FIELDS = ("direct", "indirect", "incomplete", "edge")


def content_tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def load_skills() -> tuple[dict[str, set[str]], dict[str, str]]:
    descriptions: dict[str, set[str]] = {}
    modes: dict[str, str] = {}
    registry = json.loads((REPO_ROOT / "upstream-sources.json").read_text())
    modes = {row["skill"]: row["mode"] for row in registry["sources"]}
    for path in SKILLS_DIR.iterdir():
        skill_md = path / "SKILL.md"
        if not skill_md.is_file():
            continue
        match = FRONTMATTER_RE.match(skill_md.read_text())
        if not match:
            continue
        description = str(yaml.safe_load(match.group(1)).get("description", ""))
        descriptions[path.name] = content_tokens(description + " " + path.name.replace("-", " "))
    return descriptions, modes


def score(case: str, description_tokens: set[str]) -> float:
    case_tokens = content_tokens(case)
    if not case_tokens:
        return 0.0
    return len(case_tokens & description_tokens) / len(case_tokens)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--margin", type=float, default=0.20)
    args = parser.parse_args()

    if not CASES.is_file():
        print(f"[ERROR] missing {CASES.relative_to(REPO_ROOT)}")
        return 1

    descriptions, modes = load_skills()
    # The EGA routing metadata now covers the full catalog, so the trigger
    # suite must cover every skill, not only the adapted/original ones.
    expected = sorted(descriptions)

    cases = json.loads(CASES.read_text())
    if not isinstance(cases, list):
        print("[ERROR] trigger-cases.json must be a JSON array")
        return 1

    errors: list[str] = []
    warnings: list[str] = []

    seen = [c.get("skill") for c in cases]
    if sorted(seen) != expected:
        missing = sorted(set(expected) - set(seen))
        extra = sorted(set(seen) - set(expected))
        if missing:
            errors.append(f"suite is missing skills: {missing}")
        if extra:
            errors.append(f"suite has unknown skills: {extra}")

    for case in cases:
        skill = case.get("skill")
        if skill not in descriptions:
            errors.append(f"{skill}: unknown target skill")
            continue
        for field in TEXT_FIELDS:
            if not isinstance(case.get(field), str) or not case[field].strip():
                errors.append(f"{skill}: missing or empty field '{field}'")
        for field, example in (("negative_expected", "negative"), ("collision_expected", "collision")):
            expected = case.get(field)
            if expected is None:
                # Explicit no-neighbor sentinel: the example must still be a
                # meaningful request for something other than the target.
                example_text = case.get(example, "")
                if len(content_tokens(example_text)) < 3:
                    errors.append(f"{skill}.{example}: needs at least three content words when no competing skill exists")
                elif score(example_text, descriptions[skill]) >= 0.5:
                    errors.append(f"{skill}.{example}: describes the target skill but declares no competing skill")
            elif not isinstance(expected, str) or not expected.strip():
                errors.append(f"{skill}: field '{field}' must be a skill name or null")
            elif expected not in descriptions:
                errors.append(f"{skill}: '{expected}' is not a catalog skill")
        for field in POSITIVE_FIELDS:
            minimum = 1 if field == "incomplete" else 3
            if isinstance(case.get(field), str) and len(content_tokens(case[field])) < minimum:
                errors.append(f"{skill}.{field}: too few content words to test routing")

        neighbors = [case.get("negative_expected"), case.get("collision_expected")]
        for field in POSITIVE_FIELDS:
            text = case.get(field, "")
            target = score(text, descriptions[skill])
            for neighbor in neighbors:
                if neighbor in descriptions and score(text, descriptions[neighbor]) - target >= args.margin:
                    warnings.append(
                        f"{skill}.{field}: words sit closer to {neighbor} "
                        f"({score(text, descriptions[neighbor]):.2f} vs {target:.2f})"
                    )
        for field, expected in (("negative", case.get("negative_expected")),
                                ("collision", case.get("collision_expected"))):
            if expected not in descriptions:
                continue
            text = case.get(field, "")
            if score(text, descriptions[skill]) - score(text, descriptions[expected]) >= args.margin:
                warnings.append(
                    f"{skill}.{field}: words sit closer to the target than to {expected} "
                    f"({score(text, descriptions[skill]):.2f} vs {score(text, descriptions[expected]):.2f})"
                )

    for message in warnings:
        print(f"[INFO] {message}")
    for message in errors:
        print(f"[ERROR] {message}")
    if errors:
        print(f"\nFAIL: {len(errors)} structural error(s)")
        return 1
    print(f"\nOK: {len(cases)} skills, {len(cases) * 6} trigger cases, "
          f"{len(warnings)} informational lexical note(s) at margin {args.margin}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
