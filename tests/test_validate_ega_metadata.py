"""Behavior tests for validate_ega_metadata.py (EGA routing-metadata guard).

The EGA runtime/schema remains canonical; these tests pin the source-side
compatibility guard so a metadata regression fails in CI before the catalog
reaches the EGA importer.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validate_ega_metadata  # noqa: E402


def write_skill(root: Path, name: str, ega_yaml: str) -> None:
    skill_dir = root / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\ndescription: test\n---\n")
    if ega_yaml is not None:
        (skill_dir / "ega.yaml").write_text(ega_yaml)


class TestValidateSkill(unittest.TestCase):
    def _run(self, ega_yaml, name="demo-skill"):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_skill(root, name, ega_yaml)
            with mock.patch.object(validate_ega_metadata, "SKILLS_DIR", root / "skills"):
                with mock.patch.object(validate_ega_metadata, "errors", []) as errs:
                    validate_ega_metadata.check_skill(name)
            return errs

    def test_valid_minimal(self):
        errs = self._run("schema_version: 1\n")
        self.assertEqual(errs, [])

    def test_valid_full(self):
        text = (
            "schema_version: 1\n"
            "domains: [Testing]\n"
            "platforms: [web]\n"
            "frameworks: [typescript]\n"
            "aliases: [my-alias]\n"
            "triggers:\n  - 'test driven development'\n"
            "anti_triggers:\n  - 'unit tests'\n"
        )
        errs = self._run(text)
        self.assertEqual(errs, [])

    def test_missing_schema_version(self):
        errs = self._run("triggers:\n  - 'tdd'\n")
        self.assertTrue(any("schema_version" in e for e in errs), errs)

    def test_wrong_schema_version(self):
        errs = self._run("schema_version: 2\n")
        self.assertTrue(any("schema_version: 1" in e for e in errs), errs)

    def test_unsupported_key(self):
        errs = self._run("schema_version: 1\nfuture_key: [x]\n")
        self.assertTrue(any("future_key" in e and "not supported" in e for e in errs), errs)

    def test_identifier_not_array(self):
        errs = self._run("schema_version: 1\ndomains: testing\n")
        self.assertTrue(any("domains" in e and "array" in e for e in errs), errs)

    def test_identifier_bad_format(self):
        errs = self._run("schema_version: 1\naliases: ['has spaces']\n")
        self.assertTrue(any("routing identifier" in e for e in errs), errs)

    def test_identifier_bad_chars(self):
        errs = self._run("schema_version: 1\ndomains: ['UPPER']\n")
        # uppercase is lowercased by normalization, so this is valid
        self.assertEqual(errs, [])

    def test_identifier_too_long(self):
        errs = self._run("schema_version: 1\naliases: ['" + "a" * 65 + "']\n")
        self.assertTrue(any("routing identifier" in e for e in errs), errs)

    def test_trigger_not_string(self):
        errs = self._run("schema_version: 1\ntriggers: [42]\n")
        self.assertTrue(any("triggers" in e and "strings" in e for e in errs), errs)

    def test_trigger_empty(self):
        errs = self._run("schema_version: 1\ntriggers: ['   ']\n")
        self.assertTrue(any("empty trigger" in e for e in errs), errs)

    def test_anti_trigger_not_string(self):
        errs = self._run("schema_version: 1\nanti_triggers: [true]\n")
        self.assertTrue(any("anti_triggers" in e and "strings" in e for e in errs), errs)

    def test_yaml_not_mapping(self):
        errs = self._run("- just\n- a\n- list\n")
        self.assertTrue(any("mapping" in e for e in errs), errs)

    def test_yaml_unparseable(self):
        errs = self._run("schema_version: 1\n  bad indent: [\n")
        self.assertTrue(any("parsed" in e for e in errs), errs)

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_skill(root, "demo-skill", None)
            with mock.patch.object(validate_ega_metadata, "SKILLS_DIR", root / "skills"):
                with mock.patch.object(validate_ega_metadata, "errors", []) as errs:
                    validate_ega_metadata.check_skill("demo-skill")
            self.assertTrue(any("missing ega.yaml" in e for e in errs), errs)


class TestAliasUniqueness(unittest.TestCase):
    def test_conflict_detected(self):
        metadata = {
            "skill-a": {"aliases": ["shared-alias"]},
            "skill-b": {"aliases": ["shared-alias"]},
        }
        with mock.patch.object(validate_ega_metadata, "errors", []) as errs:
            validate_ega_metadata.check_alias_uniqueness(metadata)
        self.assertTrue(any("E_ALIAS_CONFLICT" in e for e in errs), errs)

    def test_same_skill_idempotent(self):
        metadata = {"skill-a": {"aliases": ["shared-alias"]}}
        with mock.patch.object(validate_ega_metadata, "errors", []) as errs:
            validate_ega_metadata.check_alias_uniqueness(metadata)
        self.assertEqual(errs, [])

    def test_distinct_aliases_ok(self):
        metadata = {
            "skill-a": {"aliases": ["alias-a"]},
            "skill-b": {"aliases": ["alias-b"]},
        }
        with mock.patch.object(validate_ega_metadata, "errors", []) as errs:
            validate_ega_metadata.check_alias_uniqueness(metadata)
        self.assertEqual(errs, [])


class TestCatalogCoverage(unittest.TestCase):
    def test_every_skill_has_valid_ega_yaml(self):
        root = Path(__file__).resolve().parents[1]
        with mock.patch.object(validate_ega_metadata, "REPO_ROOT", root), \
             mock.patch.object(validate_ega_metadata, "SKILLS_DIR", root / "skills"):
            with mock.patch.object(validate_ega_metadata, "errors", []) as errs:
                validate_ega_metadata.main()
        self.assertEqual(errs, [], errs)


if __name__ == "__main__":
    unittest.main()
