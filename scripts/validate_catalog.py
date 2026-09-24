#!/usr/bin/env python3
"""Validate the skill catalog structure, metadata, and provenance.

Checks:
  * plugin.json is valid and has the required identity fields
  * every skill has SKILL.md with only name + description frontmatter
  * skill name matches its directory and follows naming rules
  * every skill has agents/openai.yaml with valid interface metadata
  * every relative reference in a skill resolves
  * no empty references/scripts/assets directories
  * no placeholders, TODOs, or Cursor-specific coupling
  * upstream-sources.json covers every skill exactly once

Usage:
    python3 scripts/validate_catalog.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
BARE_REF_RE = re.compile(r"(?<![\w/])((?:references|scripts|assets)/[\w./-]+)")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
TRAILING_PUNCT = ".,;:)"

ALLOWED_FRONTMATTER = {"name", "description"}
RESOURCE_DIRS = ("references", "scripts", "assets")

PLACEHOLDER_PATTERNS = [
    re.compile(r"\bTODO\b"),
    re.compile(r"\bFIXME\b"),
    re.compile(r"\[TODO"),
    re.compile(r"\bcoming soon\b", re.IGNORECASE),
]

LEAK_PATTERNS = [
    re.compile(r"\bCursor\b"),
    re.compile(r"~/\.cursor"),
    re.compile(r"\bpstack\b", re.IGNORECASE),
    re.compile(r"\bsubagent_type\b"),
    re.compile(r"\bdisable-model-invocation\b"),
    re.compile(r"\b(?:claude|gpt|o[34])-(?:opus|sonnet|haiku|\d)"),
    re.compile(r"\bgrok-\d"),
    re.compile(r"\bpoteto-mode\b"),
    re.compile(r"\bCursor built-in\b"),
    re.compile(r"\bTask tool\b"),
]

errors: list[str] = []
warnings: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def warn(message: str) -> None:
    warnings.append(message)


def check_plugin() -> None:
    path = REPO_ROOT / "plugin.json"
    if not path.is_file():
        fail("plugin.json: missing")
        return
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        fail(f"plugin.json: invalid JSON: {exc}")
        return
    for key in ("name", "version", "description", "license", "skills"):
        if key not in data:
            fail(f"plugin.json: missing required field '{key}'")
    if data.get("skills") != "./skills/":
        fail("plugin.json: 'skills' must be './skills/'")
    if not isinstance(data.get("interface"), dict):
        fail("plugin.json: missing 'interface' object")


def parse_skill_md(path: Path) -> tuple[dict, str]:
    text = path.read_text()
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("no YAML frontmatter")
    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict):
        raise ValueError("frontmatter is not a mapping")
    return data, text[match.end():]


def check_skill(name: str) -> None:
    skill_dir = SKILLS_DIR / name
    skill_md = skill_dir / "SKILL.md"

    try:
        frontmatter, body = parse_skill_md(skill_md)
    except (ValueError, yaml.YAMLError) as exc:
        fail(f"{name}: SKILL.md frontmatter invalid: {exc}")
        return

    extra = set(frontmatter) - ALLOWED_FRONTMATTER
    if extra:
        fail(f"{name}: unexpected frontmatter keys: {sorted(extra)}")
    if frontmatter.get("name") != name:
        fail(f"{name}: frontmatter name '{frontmatter.get('name')}' != directory")
    if not NAME_RE.match(name) or len(name) > 64:
        fail(f"{name}: invalid skill name")

    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        fail(f"{name}: missing description")
    else:
        if len(description) > 1024:
            fail(f"{name}: description too long ({len(description)})")
        if "<" in description or ">" in description:
            fail(f"{name}: description contains angle brackets")

    # agents/openai.yaml
    yaml_path = skill_dir / "agents" / "openai.yaml"
    if not yaml_path.is_file():
        fail(f"{name}: missing agents/openai.yaml")
    else:
        try:
            interface = yaml.safe_load(yaml_path.read_text()).get("interface", {})
        except (yaml.YAMLError, AttributeError) as exc:
            fail(f"{name}: agents/openai.yaml invalid: {exc}")
            interface = {}
        for field in ("display_name", "short_description", "default_prompt"):
            if not isinstance(interface.get(field), str) or not interface.get(field):
                fail(f"{name}: agents/openai.yaml missing interface.{field}")
        short = interface.get("short_description", "")
        if isinstance(short, str) and not (25 <= len(short) <= 64):
            fail(f"{name}: short_description length {len(short)} outside 25-64")
        prompt = interface.get("default_prompt", "")
        if isinstance(prompt, str) and f"${name}" not in prompt:
            fail(f"{name}: default_prompt must mention ${name}")

    # resource directories
    for folder in RESOURCE_DIRS:
        folder_path = skill_dir / folder
        if folder_path.is_dir() and not any(folder_path.rglob("*")):
            fail(f"{name}: empty {folder}/ directory")

    # reference integrity + leak scan
    for md in sorted(skill_dir.rglob("*.md")):
        raw = md.read_text()
        text = FENCE_RE.sub("", raw)
        for match in LINK_RE.finditer(text):
            check_reference(name, skill_dir, md, match.group(1))
        for match in BARE_REF_RE.finditer(text):
            check_reference(name, skill_dir, md, match.group(1))
        for pattern in LEAK_PATTERNS:
            found = pattern.search(text)
            if found:
                fail(f"{name}: Cursor-specific leak '{found.group(0)}' in {md.relative_to(skill_dir)}")

    for pattern in PLACEHOLDER_PATTERNS:
        found = pattern.search(body)
        if found:
            fail(f"{name}: placeholder '{found.group(0)}' in SKILL.md body")


def check_reference(skill: str, skill_dir: Path, source_file: Path, target: str) -> None:
    target = target.strip().rstrip(TRAILING_PUNCT)
    if target.startswith(("http://", "https://", "#", "mailto:")):
        return
    target = target.split("#", 1)[0].strip()
    if not target:
        return
    # A resource path may be written relative to the referencing file or to the
    # skill root. Accept either when it resolves inside the repository.
    candidates = [source_file.parent / target, skill_dir / target]
    for candidate in candidates:
        resolved = candidate.resolve()
        try:
            resolved.relative_to(REPO_ROOT)
        except ValueError:
            continue
        if resolved.exists():
            return
    fail(f"{skill}: broken reference '{target}' in {source_file.relative_to(REPO_ROOT)}")


def check_provenance() -> None:
    path = REPO_ROOT / "upstream-sources.json"
    if not path.is_file():
        fail("upstream-sources.json: missing")
        return
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        fail(f"upstream-sources.json: invalid JSON: {exc}")
        return
    sources = data.get("sources")
    if not isinstance(sources, list):
        fail("upstream-sources.json: missing 'sources' array")
        return
    recorded = [s.get("skill") for s in sources]
    if len(recorded) != len(set(recorded)):
        fail("upstream-sources.json: duplicate skill entries")
    catalog = sorted(p.name for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file())
    if sorted(recorded) != catalog:
        missing = sorted(set(catalog) - set(recorded))
        extra = sorted(set(recorded) - set(catalog))
        if missing:
            fail(f"upstream-sources.json: missing entries: {missing}")
        if extra:
            fail(f"upstream-sources.json: unknown entries: {extra}")
    for source in sources:
        mode = source.get("mode")
        if mode not in {"copied", "adapted", "original"}:
            fail(f"upstream-sources.json: {source.get('skill')}: bad mode '{mode}'")
        if mode in {"copied", "adapted"}:
            if not source.get("source_commit"):
                fail(f"upstream-sources.json: {source.get('skill')}: missing source_commit")
            if not source.get("license"):
                fail(f"upstream-sources.json: {source.get('skill')}: missing license")


def main() -> int:
    check_plugin()
    if not SKILLS_DIR.is_dir():
        fail("skills/: missing")
        skill_names: list[str] = []
    else:
        skill_names = sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir())
        if len(skill_names) != len(set(skill_names)):
            fail("skills/: duplicate names")
        for name in skill_names:
            if not (SKILLS_DIR / name / "SKILL.md").is_file():
                fail(f"{name}: no SKILL.md")
                continue
            check_skill(name)
    check_provenance()

    for message in warnings:
        print(f"[WARN] {message}")
    for message in errors:
        print(f"[ERROR] {message}")
    if errors:
        print(f"\nFAIL: {len(errors)} error(s) across {len(skill_names)} skills")
        return 1
    print(f"\nOK: {len(skill_names)} skills validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
