#!/usr/bin/env python3
"""Source-side compatibility guard for EGA routing metadata (ega.yaml).

The EGA runtime and its V1 schema (SPEC-001 §5.1.8–§5.1.11) remain canonical.
This script is a small, deterministic source-side validator that checks the
repository's ega.yaml files against the EGA routing-metadata contract so a
metadata regression is caught in CI before the catalog reaches the EGA
importer. It does not copy EGA runtime code and does not replace the
canonical schema; it is a compatibility guard.

Checks per skill:
  * ega.yaml parses as a YAML mapping
  * schema_version == 1
  * only supported V1 keys are present
  * domains/platforms/frameworks/aliases are arrays of routing identifiers
    matching ^[a-z0-9][a-z0-9._+-]{0,63}$ (after trim + ASCII-lowercase)
  * triggers/anti_triggers are arrays of non-empty strings
  * no duplicate values within a set after normalization
  * aliases are globally unique across the catalog (E_ALIAS_CONFLICT guard)

Catalog-level check:
  * every skill in the catalog has a valid ega.yaml

Usage:
    python3 scripts/validate_ega_metadata.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"

SCHEMA_VERSION = 1
SUPPORTED_KEYS = {
    "schema_version",
    "domains",
    "platforms",
    "frameworks",
    "aliases",
    "triggers",
    "anti_triggers",
}
IDENTIFIER_KEYS = ("domains", "platforms", "frameworks", "aliases")
TRIGGER_KEYS = ("triggers", "anti_triggers")

# SPEC-001 §5.1.9: routing identifier format.
ROUTING_IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9._+-]{0,63}$")

errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def normalize_identifier_set(entries: list, field: str, skill: str) -> list[str]:
    """Validate an identifier set the way EGA normalizes it (§5.1.9)."""
    normalized: list[str] = []
    for entry in entries:
        if not isinstance(entry, str):
            fail(f"{skill}: ega.yaml {field} entries must be strings, got {type(entry).__name__}")
            continue
        canonical = entry.strip().lower()
        if not ROUTING_IDENTIFIER_RE.match(canonical):
            fail(
                f"{skill}: ega.yaml {field} entry {entry!r} is not a valid routing "
                f"identifier (expected ^[a-z0-9][a-z0-9._+-]{{0,63}}$)"
            )
            continue
        normalized.append(canonical)
    return sorted(set(normalized))


def normalize_trigger_set(entries: list, field: str, skill: str) -> list[str]:
    """Validate a trigger set the way EGA normalizes it (§5.1.10)."""
    normalized: list[str] = []
    for entry in entries:
        if not isinstance(entry, str):
            fail(f"{skill}: ega.yaml {field} entries must be strings, got {type(entry).__name__}")
            continue
        canonical = entry.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not canonical:
            fail(f"{skill}: ega.yaml {field} contains an empty trigger after normalization")
            continue
        normalized.append(canonical)
    return sorted(set(normalized))


def check_skill(name: str) -> dict:
    """Validate one skill's ega.yaml; return the parsed metadata dict."""
    path = SKILLS_DIR / name / "ega.yaml"
    if not path.is_file():
        fail(f"{name}: missing ega.yaml (every EGA-routed skill needs routing metadata)")
        return {}

    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        fail(f"{name}: ega.yaml must be valid UTF-8 text")
        return {}

    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        fail(f"{name}: ega.yaml could not be parsed as YAML: {exc}")
        return {}

    if not isinstance(parsed, dict):
        fail(f"{name}: ega.yaml must be a YAML mapping at the top level")
        return {}

    version = parsed.get("schema_version")
    if version != SCHEMA_VERSION:
        fail(f"{name}: ega.yaml must declare schema_version: {SCHEMA_VERSION} (got {version!r})")
        return {}

    unsupported = sorted(set(parsed) - SUPPORTED_KEYS)
    if unsupported:
        fail(f"{name}: ega.yaml key(s) {unsupported} are not supported in V1")

    metadata: dict = {}
    for field in IDENTIFIER_KEYS:
        value = parsed.get(field)
        if value is None:
            metadata[field] = []
            continue
        if not isinstance(value, list):
            fail(f"{name}: ega.yaml {field} must be an array of identifier strings")
            metadata[field] = []
            continue
        metadata[field] = normalize_identifier_set(value, field, name)

    for field in TRIGGER_KEYS:
        value = parsed.get(field)
        if value is None:
            metadata[field] = []
            continue
        if not isinstance(value, list):
            fail(f"{name}: ega.yaml {field} must be an array of strings")
            metadata[field] = []
            continue
        metadata[field] = normalize_trigger_set(value, field, name)

    return metadata


def check_alias_uniqueness(all_metadata: dict[str, dict]) -> None:
    """Guard E_ALIAS_CONFLICT: an alias must map to at most one skill (§5.1.11)."""
    owners: dict[str, str] = {}
    for skill in sorted(all_metadata):
        for alias in all_metadata[skill].get("aliases", []):
            owner = owners.get(alias)
            if owner is not None and owner != skill:
                fail(
                    f"{skill}: alias {alias!r} is already owned by {owner} "
                    f"(E_ALIAS_CONFLICT)"
                )
            else:
                owners[alias] = skill


def main() -> int:
    if not SKILLS_DIR.is_dir():
        fail("skills/: missing")
        print(f"[ERROR] {len(errors)} error(s)")
        return 1

    skill_names = sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir())
    all_metadata: dict[str, dict] = {}
    for name in skill_names:
        if not (SKILLS_DIR / name / "SKILL.md").is_file():
            continue
        all_metadata[name] = check_skill(name)

    check_alias_uniqueness(all_metadata)

    for message in errors:
        print(f"[ERROR] {message}")
    if errors:
        print(f"\nFAIL: {len(errors)} error(s) across {len(all_metadata)} skills")
        return 1
    print(f"\nOK: {len(all_metadata)} skills have valid EGA routing metadata (schema_version {SCHEMA_VERSION})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
