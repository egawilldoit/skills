#!/usr/bin/env python3
"""Validate plugin.json against the Agent Plugins 1.0.0 schema.

Source of truth:
  canonical schema URL: https://agent-plugins.org/schemas/1.0.0/plugin.schema.json
  specification:        https://agent-plugins.org/specification
  OpenAI extension docs: https://developers.openai.com/plugins/build/plugins

A local copy of the exact 1.0.0 schema is vendored at
references/agent-plugin-schema-1.0.0.json so validation is deterministic and
offline. The repository pins the vendored file's expected SHA-256 digest at
references/agent-plugin-schema-1.0.0.sha256; this script refuses to run if the
vendored bytes no longer match that pin. The pin is integrity against local
drift, not a live comparison against the canonical URL (no network fetch is
performed).

Layers:
  1. Vendored-schema integrity: SHA-256 of the vendored schema must equal the
     committed pin (references/agent-plugin-schema-1.0.0.sha256), and the
     schema's $id must be the canonical 1.0.0 identifier.
  2. JSON Schema validation against the vendored 1.0.0 schema (closed manifest:
     only $schema, name, version, description, author, homepage, repository,
     license, keywords, extensions are permitted at the root).
  2. Spec-level checks the schema cannot express, with clear diagnostics:
     - $schema equals the canonical 1.0.0 identifier
     - no obsolete root `skills` or root `interface`
     - `extensions` is an object of objects
     - OpenAI presentation metadata lives under `extensions.com.openai.interface`
     - skills are auto-discovered from `skills/`, so no `skills` field is allowed

Usage:
    python3 scripts/validate_plugin_manifest.py [path/to/plugin.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO_ROOT / "plugin.json"
VENDORED_SCHEMA = REPO_ROOT / "references" / "agent-plugin-schema-1.0.0.json"
SCHEMA_DIGEST_PIN = REPO_ROOT / "references" / "agent-plugin-schema-1.0.0.sha256"

CANONICAL_SCHEMA_ID = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
ALLOWED_ROOT_FIELDS = {
    "$schema", "name", "version", "description", "author", "homepage",
    "repository", "license", "keywords", "extensions",
}
OBSOLETE_ROOT_FIELDS = {"skills", "interface", "mcpServers", "hooks", "apps"}


def verify_schema_pin() -> None:
    """Refuse to validate if the vendored schema diverges from its pinned digest."""
    import hashlib

    if not SCHEMA_DIGEST_PIN.is_file():
        raise SystemExit(f"schema digest pin missing: {SCHEMA_DIGEST_PIN}")
    expected = SCHEMA_DIGEST_PIN.read_text().split()[0].strip().lower()
    actual = hashlib.sha256(VENDORED_SCHEMA.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(
            f"vendored schema digest {actual} does not match pinned {expected}; "
            f"update both {VENDORED_SCHEMA.name} and {SCHEMA_DIGEST_PIN.name} together"
        )


def load_schema() -> dict:
    verify_schema_pin()
    schema = json.loads(VENDORED_SCHEMA.read_text())
    if schema.get("$id") != CANONICAL_SCHEMA_ID:
        raise SystemExit(
            f"vendored schema $id is {schema.get('$id')!r}, expected {CANONICAL_SCHEMA_ID!r}"
        )
    const = schema.get("properties", {}).get("$schema", {}).get("const")
    if const != CANONICAL_SCHEMA_ID:
        raise SystemExit(
            f"vendored schema $schema const is {const!r}, expected {CANONICAL_SCHEMA_ID!r}"
        )
    return schema


def make_validator(schema: dict):
    """Return a validator instance that understands this schema's draft."""
    try:
        from jsonschema import Draft202012Validator

        return Draft202012Validator(schema)
    except ImportError:
        pass
    try:
        from jsonschema import validators

        validator_cls = validators.validator_for(schema)
        validator_cls.check_schema(schema)
        return validator_cls(schema)
    except Exception as exc:  # pragma: no cover - environment dependent
        raise SystemExit(
            "jsonschema is required (jsonschema>=4 recommended). "
            f"Import failed: {exc}"
        )


def spec_checks(data: dict) -> list[str]:
    errors: list[str] = []

    if data.get("$schema") != CANONICAL_SCHEMA_ID:
        errors.append(
            f"$schema must be {CANONICAL_SCHEMA_ID!r}, got {data.get('$schema')!r}"
        )

    for field in sorted(OBSOLETE_ROOT_FIELDS):
        if field in data:
            if field in {"skills", "interface"}:
                errors.append(
                    f"obsolete root field '{field}' is not part of the portable manifest; "
                    "skills are auto-discovered from skills/ and OpenAI metadata lives "
                    "under extensions.com.openai"
                )
            else:
                errors.append(f"obsolete root field '{field}' is not permitted")

    unknown = set(data) - ALLOWED_ROOT_FIELDS
    for field in sorted(unknown):
        errors.append(f"unknown root field '{field}'")

    extensions = data.get("extensions")
    if extensions is not None:
        if not isinstance(extensions, dict):
            errors.append("extensions must be an object")
        else:
            for namespace, value in extensions.items():
                if not isinstance(value, dict):
                    errors.append(f"extensions['{namespace}'] must be an object")
            openai_ext = extensions.get("com.openai")
            if openai_ext is not None:
                if not isinstance(openai_ext, dict):
                    errors.append("extensions['com.openai'] must be an object")
                else:
                    interface = openai_ext.get("interface")
                    if interface is not None:
                        if not isinstance(interface, dict):
                            errors.append("extensions['com.openai'].interface must be an object")
                        else:
                            for key in ("displayName", "shortDescription", "longDescription",
                                        "developerName", "category", "capabilities",
                                        "defaultPrompt"):
                                if key in interface and not isinstance(
                                    interface[key], (str, list)
                                ):
                                    errors.append(
                                        f"extensions['com.openai'].interface.{key} has wrong type"
                                    )

    if "skills" not in data:
        pass  # expected: portable discovery, no declaration needed

    return errors


def validate(manifest_path: Path) -> list[str]:
    if not manifest_path.is_file():
        return [f"{manifest_path}: missing"]

    try:
        data = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        return [f"{manifest_path}: invalid JSON: {exc}"]

    if not isinstance(data, dict):
        return [f"{manifest_path}: top-level value must be an object"]

    errors = spec_checks(data)

    schema = load_schema()
    validator = make_validator(schema)
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        location = "/".join(str(p) for p in error.path) or "(root)"
        errors.append(f"schema: {location}: {error.message}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?", default=str(DEFAULT_MANIFEST))
    args = parser.parse_args()

    errors = validate(Path(args.manifest))
    for message in errors:
        print(f"[ERROR] {message}")
    if errors:
        print(f"\nFAIL: plugin manifest is not Agent Plugins 1.0.0 conformant ({len(errors)} error(s))")
        return 1
    print("OK: plugin.json conforms to Agent Plugins 1.0.0 (skills auto-discovered from skills/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
