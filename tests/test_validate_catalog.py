import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validate_catalog  # noqa: E402


class TestPluginName(unittest.TestCase):
    def test_plugin_name_from_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "plugin.json").write_text(json.dumps({"name": "test-plugin"}))
            with mock.patch.object(validate_catalog, "REPO_ROOT", root):
                self.assertEqual(validate_catalog.plugin_name(), "test-plugin")

    def test_plugin_name_missing_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(validate_catalog, "REPO_ROOT", Path(tmp)):
                self.assertEqual(validate_catalog.plugin_name(), "unknown-plugin")


class TestCombinedIdentity(unittest.TestCase):
    def _run_check(self, skill, plugin):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "skills" / skill
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                f"---\nname: {skill}\ndescription: test skill\n---\n"
            )
            with mock.patch.object(validate_catalog, "REPO_ROOT", root), \
                 mock.patch.object(validate_catalog, "SKILLS_DIR", root / "skills"):
                with mock.patch.object(validate_catalog, "errors", []) as errs:
                    with mock.patch.object(validate_catalog, "warnings", []):
                        validate_catalog.check_skill(skill, plugin)
            return errs

    def test_combined_identity_at_boundary_passes(self):
        plugin = "ega-skills"
        # 63 chars combined: allowed (<= 64).
        pad = 63 - len(plugin) - 1
        skill = "a" + "-" + "a" * (pad - 2)
        skill = "a" * pad
        errs = self._run_check(skill, plugin)
        self.assertFalse([e for e in errs if "identity too long" in e], errs)

    def test_combined_identity_over_limit_fails(self):
        plugin = "ega-skills"
        skill = "a" * 56  # 10 + 1 + 56 = 67 chars combined
        errs = self._run_check(skill, plugin)
        identity = f"{plugin}:{skill}"
        self.assertTrue(any("identity too long" in e for e in errs), errs)
        for needle in (identity, f"skill={skill}", f"plugin={plugin}",
                       f"length={len(identity)}", "max=64"):
            self.assertTrue(any(needle in e for e in errs), errs)

    def test_combined_identity_at_64_passes(self):
        plugin = "ega-skills"
        pad = 64 - len(plugin) - 1
        skill = "a" * pad  # exactly 64 combined
        errs = self._run_check(skill, plugin)
        self.assertFalse([e for e in errs if "identity too long" in e], errs)


class TestLongestIdentity(unittest.TestCase):
    def test_catalog_identities_within_limit(self):
        repo = Path(__file__).resolve().parents[1]
        manifest = json.loads((repo / "plugin.json").read_text())
        plugin = manifest["name"]
        skills = sorted(p.name for p in (repo / "skills").iterdir() if p.is_dir())
        identities = [f"{plugin}:{name}" for name in skills]
        # Zero skills is a valid catalog state; every identity that does exist
        # must still fit the 64-character submission constraint.
        for identity in identities:
            self.assertLessEqual(len(identity), 64, identity)


class TestCatalogIntegrity(unittest.TestCase):
    REPO = Path(__file__).resolve().parents[1]

    def _run_main(self, root, skills_dir):
        with mock.patch.object(validate_catalog, "REPO_ROOT", root), \
             mock.patch.object(validate_catalog, "SKILLS_DIR", skills_dir), \
             mock.patch.object(validate_catalog, "errors", []) as errs, \
             mock.patch.object(validate_catalog, "warnings", []):
            return validate_catalog.main(), errs

    def test_zero_skill_catalog_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skills.mkdir()
            (root / "plugin.json").write_text((self.REPO / "plugin.json").read_text())
            (root / "upstream-sources.json").write_text(
                json.dumps({"sources": []})
            )
            code, errs = self._run_main(root, skills)
            self.assertEqual(code, 0, errs)
            self.assertEqual(errs, [], errs)

    def test_stale_provenance_entry_fails_on_empty_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skills.mkdir()
            (root / "plugin.json").write_text((self.REPO / "plugin.json").read_text())
            (root / "upstream-sources.json").write_text(
                json.dumps({"sources": [{"skill": "ghost", "mode": "original"}]})
            )
            code, errs = self._run_main(root, skills)
            self.assertEqual(code, 1)
            self.assertTrue(any("unknown entries" in e for e in errs), errs)


if __name__ == "__main__":
    unittest.main()
