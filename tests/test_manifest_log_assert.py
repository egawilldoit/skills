"""Tests for validate_plugin_manifest.py, log.sh, and assert_checkout_sha.py."""

import hashlib
import json
import re
import shutil
import stat
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
        other = subprocess.run(["git", "rev-parse", "HEAD~1"], cwd=REPO_ROOT,
                               capture_output=True, text=True).stdout.strip()
        proc = self.run_assert("--expected", other, "--mode", "exact-head")
        self.assertEqual(proc.returncode, 1)

    def test_merge_result_mode_requires_difference(self):
        proc = self.run_assert("--expected", self.HEAD, "--mode", "merge-result")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("synthetic merge", proc.stderr)

    def test_identity_block_present(self):
        proc = self.run_assert("--expected", self.HEAD, "--event", "push")
        for needle in ("EVENT:", "EXPECTED SHA:", "EXECUTED SHA:"):
            self.assertIn(needle, proc.stdout)


class TestRecordEvidenceLog(unittest.TestCase):
    LOG_SH = REPO_ROOT / "skills" / "record-evidence" / "scripts" / "log.sh"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="logsh-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def run_log(self, *args):
        return subprocess.run(["bash", str(self.LOG_SH), *args],
                              capture_output=True, text=True)

    def test_header_created_on_first_use(self):
        log = self.tmp / "decisions.tsv"
        proc = self.run_log(str(log), "phase", "decision", "why", "ev", "result")
        self.assertEqual(proc.returncode, 0)
        header = log.read_text().splitlines()[0]
        self.assertTrue(header.startswith("ts\tphase\tdecision\twhy\tevidence\tresult"))

    def test_row_appended_after_header(self):
        log = self.tmp / "decisions.tsv"
        self.run_log(str(log), "p1", "d1", "w1", "e1", "r1")
        self.run_log(str(log), "p2", "d2", "w2", "e2", "r2")
        lines = log.read_text().splitlines()
        self.assertEqual(len(lines), 3)  # header + 2 rows
        self.assertIn("p2\td2\tw2\te2\tr2", lines[2])

    def test_tab_and_newline_sanitized(self):
        log = self.tmp / "decisions.tsv"
        self.run_log(str(log), "p\twith\ttabs", "decision", "why", "ev", "res")
        lines = log.read_text().splitlines()
        self.assertEqual(len(lines), 2)  # one physical row
        cells = lines[1].split("\t")
        self.assertEqual(cells[1], "p with tabs")
        self.assertNotIn("\n", cells[1])

    def test_spreadsheet_formula_neutralized(self):
        log = self.tmp / "decisions.tsv"
        self.run_log(str(log), "phase", "=cmd|' /C calc'!A0", "why", "ev", "res")
        row = log.read_text().splitlines()[1]
        self.assertTrue(row.split("\t")[2].startswith("'="))

    def test_negative_starting_cell_neutralized(self):
        log = self.tmp / "decisions.tsv"
        self.run_log(str(log), "phase", "-1", "why", "ev", "res")
        self.assertTrue(log.read_text().splitlines()[1].split("\t")[2].startswith("'-"))

    def test_wrong_argcount_fails(self):
        proc = self.run_log(str(self.tmp / "x.tsv"), "only", "two")
        self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
