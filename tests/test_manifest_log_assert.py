"""Tests for validate_plugin_manifest.py and assert_checkout_sha.py."""

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import validate_plugin_manifest  # noqa: E402


class TestSchemaPin(unittest.TestCase):
    def test_vendored_schema_matches_committed_pin(self):
        # The real repository: pin file must exist and match actual bytes.
        actual = hashlib.sha256(
            (REPO_ROOT / "references" / "agent-plugin-schema-1.0.0.json").read_bytes()
        ).hexdigest()
        pin = (REPO_ROOT / "references" / "agent-plugin-schema-1.0.0.sha256").read_text()
        self.assertEqual(actual, pin.split()[0])

    def test_validation_refuses_tampered_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            refs = root / "references"
            refs.mkdir()
            schema = refs / "agent-plugin-schema-1.0.0.json"
            schema.write_text((REPO_ROOT / "references" / "agent-plugin-schema-1.0.0.json").read_text())
            (refs / "agent-plugin-schema-1.0.0.sha256").write_text("0" * 64)
            manifest = root / "plugin.json"
            manifest.write_text(json.dumps(
                {"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                 "name": "x", "version": "1.0"}))
            with mock.patch.object(validate_plugin_manifest, "REPO_ROOT", root), \
                 mock.patch.object(validate_plugin_manifest, "VENDORED_SCHEMA", schema), \
                 mock.patch.object(validate_plugin_manifest, "SCHEMA_DIGEST_PIN",
                                   refs / "agent-plugin-schema-1.0.0.sha256"), \
                 mock.patch.object(validate_plugin_manifest, "DEFAULT_MANIFEST", manifest):
                with self.assertRaises(SystemExit) as ctx:
                    validate_plugin_manifest.validate(manifest)
            self.assertIn("digest", str(ctx.exception))

    def test_validation_refuses_missing_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(validate_plugin_manifest, "SCHEMA_DIGEST_PIN",
                                   Path(tmp) / "missing.sha256"):
                with self.assertRaises(SystemExit):
                    validate_plugin_manifest.verify_schema_pin()

    def test_doc_does_not_overclaim_live_schema_check(self):
        doc = Path(REPO_ROOT / "scripts" / "validate_plugin_manifest.py").read_text()
        self.assertNotIn("diverges from the live canonical schema", doc)
        self.assertIn("expected SHA-256 digest", doc)


class TestManifestValidation(unittest.TestCase):
    def test_real_manifest_passes(self):
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "validate_plugin_manifest.py")],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_identity_is_short_plugin_name(self):
        manifest = json.loads((REPO_ROOT / "plugin.json").read_text())
        self.assertEqual(manifest["name"], "ega-skills")
        interface = manifest["extensions"]["com.openai"]["interface"]
        self.assertEqual(interface["displayName"], "egawilldoit skills")
        self.assertLessEqual(len(interface["shortDescription"]), 30)


class TestAssertCheckoutSha(unittest.TestCase):
    HEAD = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                          capture_output=True, text=True).stdout.strip()

    def run_assert(self, *flags):
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "assert_checkout_sha.py"), *flags],
            cwd=REPO_ROOT, capture_output=True, text=True)

    def test_exact_head_satisfied(self):
        proc = self.run_assert("--expected", self.HEAD, "--mode", "exact-head",
                               "--event", "pull_request")
        self.assertEqual(proc.returncode, 0)
        self.assertIn(self.HEAD, proc.stdout)

    def test_exact_head_mismatch_fails(self):
        # Use a self-contained temp repo so this does not depend on the
        # checkout being non-shallow.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            subprocess.run(f"git init -q -b main {repo}", shell=True, check=True)
            subprocess.run(f"git -C {repo} config user.email t@t && "
                           f"git -C {repo} config user.name t", shell=True, check=True)
            subprocess.run(f"cd {repo} && echo a > a && git add a && git commit -qm one && "
                           "echo b > b && git add b && git commit -qm two", shell=True, check=True)
            other = subprocess.run(f"git -C {repo} rev-parse HEAD~1",
                                   shell=True, capture_output=True, text=True).stdout.strip()
            proc = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / "assert_checkout_sha.py"),
                 "--expected", other, "--mode", "exact-head"],
                cwd=repo, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1)

    def test_merge_result_mode_requires_difference(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            subprocess.run(f"git init -q -b main {repo}", shell=True, check=True)
            subprocess.run(f"git -C {repo} config user.email t@t && "
                           f"git -C {repo} config user.name t", shell=True, check=True)
            subprocess.run(f"cd {repo} && echo a > a && git add a && git commit -qm one",
                           shell=True, check=True)
            head = subprocess.run(f"git -C {repo} rev-parse HEAD",
                                  shell=True, capture_output=True, text=True).stdout.strip()
            proc = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / "assert_checkout_sha.py"),
                 "--expected", head, "--mode", "merge-result"],
                cwd=repo, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("synthetic merge", proc.stderr)

    def test_identity_block_present(self):
        proc = self.run_assert("--expected", self.HEAD, "--event", "push")
        for needle in ("EVENT:", "EXPECTED SHA:", "EXECUTED SHA:"):
            self.assertIn(needle, proc.stdout)


if __name__ == "__main__":
    unittest.main()
