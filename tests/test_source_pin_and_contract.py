"""Tests for the Cursor source-pin import guard and operating-contract sync."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import import_cursor_skills  # noqa: E402
import sync_operating_contract  # noqa: E402

PIN = import_cursor_skills.SOURCE_COMMIT


def sh(cmd, cwd=None):
    proc = subprocess.run(cmd, cwd=cwd, shell=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(f"failed: {cmd}\n{proc.stderr}")
    return proc.stdout.strip()


def make_checkout(base, origin_url="https://github.com/cursor/plugins.git", pinned_head=False):
    """A git checkout whose pstack layout matches the importer's expectations.

    pinned_head: replace HEAD with a fabricated commit; the caller should
    mock import_cursor_skills.SOURCE_COMMIT to that commit's SHA so the
    "checkout == pin" path can be exercised without the real upstream
    commit object.
    """
    path = base / "checkout"
    path.mkdir(parents=True)
    sh("git init -q -b main .", cwd=path)
    sh("git config user.email t@t && git config user.name t", cwd=path)
    (path / "pstack").mkdir()
    (path / "pstack" / "skills").mkdir()
    (path / "pstack" / "skills" / "some-skill").mkdir()
    (path / "pstack" / "skills" / "some-skill" / "SKILL.md").write_text("---\nname: some-skill\ndescription: test\n---\n")
    sh("echo hi > hi.txt && git add -A && git commit -qm init", cwd=path)
    if pinned_head:
        tree = sh("git rev-parse HEAD^{tree}", cwd=path)
        fabricated = sh(f'git commit-tree {tree} -m "fabricated pin commit"', cwd=path)
        sh(f"git update-ref HEAD {fabricated}", cwd=path)
    if origin_url:
        sh(f"git remote add origin {origin_url}", cwd=path)
    return path


def fabricate_pin(checkout):
    """Return a mock context pinning SOURCE_COMMIT to the checkout's HEAD."""
    head = sh("git rev-parse HEAD", cwd=checkout)
    return mock.patch.object(import_cursor_skills, "SOURCE_COMMIT", head)


class TestSourcePinGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="srcpin-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_pinned_checkout_with_cursor_origin_passes(self):
        checkout = make_checkout(self.tmp, pinned_head=True)
        with fabricate_pin(checkout):
            import_cursor_skills.verify_source_checkout(checkout)  # no SystemExit

    def test_supported_cursor_remote_forms_pass(self):
        for url in ("https://github.com/cursor/plugins.git",
                    "git@github.com:cursor/plugins.git",
                    "ssh://git@github.com/cursor/plugins.git"):
            with self.subTest(url=url):
                checkout = make_checkout(self.tmp / url.replace(":", "_").replace("/", "_"),
                                         origin_url=url, pinned_head=True)
                with fabricate_pin(checkout):
                    import_cursor_skills.verify_source_checkout(checkout)

    def test_missing_origin_fails(self):
        checkout = make_checkout(self.tmp, origin_url=None, pinned_head=True)
        with fabricate_pin(checkout):
            with self.assertRaises(SystemExit) as ctx:
                import_cursor_skills.verify_source_checkout(checkout)
        self.assertIn("origin", str(ctx.exception).lower())

    def test_unpinned_checkout_hard_fails(self):
        checkout = make_checkout(self.tmp)
        with self.assertRaises(SystemExit) as ctx:
            import_cursor_skills.verify_source_checkout(checkout)
        message = str(ctx.exception)
        self.assertIn("refusing to import unpinned source", message)

    def test_mismatch_error_names_both_shas(self):
        checkout = make_checkout(self.tmp)
        with self.assertRaises(SystemExit) as ctx:
            import_cursor_skills.verify_source_checkout(checkout)
        message = str(ctx.exception)
        actual = sh("git rev-parse HEAD", cwd=checkout)
        self.assertIn(actual, message)
        self.assertIn(PIN, message)

    def test_wrong_origin_fails_when_sha_matches(self):
        checkout = make_checkout(self.tmp, origin_url="https://gitlab.com/evil/skills.git",
                                 pinned_head=True)
        with fabricate_pin(checkout):
            with self.assertRaises(SystemExit) as ctx:
                import_cursor_skills.verify_source_checkout(checkout)
        self.assertIn("origin", str(ctx.exception))

    def test_tracked_working_tree_modification_fails(self):
        checkout = make_checkout(self.tmp, pinned_head=True)
        with fabricate_pin(checkout):
            (checkout / "pstack/skills/some-skill/SKILL.md").write_text("dirty\n")
            with self.assertRaises(SystemExit) as ctx:
                import_cursor_skills.verify_source_checkout(checkout)
        self.assertIn("tracked modifications", str(ctx.exception))

    def test_staged_tracked_modification_fails(self):
        checkout = make_checkout(self.tmp, pinned_head=True)
        with fabricate_pin(checkout):
            (checkout / "pstack/skills/some-skill/SKILL.md").write_text("staged dirty\n")
            sh("git add pstack/skills/some-skill/SKILL.md", cwd=checkout)
            with self.assertRaises(SystemExit) as ctx:
                import_cursor_skills.verify_source_checkout(checkout)
        self.assertIn("tracked modifications", str(ctx.exception))

    def test_untracked_file_fails(self):
        checkout = make_checkout(self.tmp, pinned_head=True)
        with fabricate_pin(checkout):
            (checkout / "untracked.txt").write_text("untracked\n")
            with self.assertRaises(SystemExit) as ctx:
                import_cursor_skills.verify_source_checkout(checkout)
        self.assertIn("untracked files", str(ctx.exception))

    def test_not_a_checkout_fails(self):
        with self.assertRaises(SystemExit):
            import_cursor_skills.verify_source_checkout(self.tmp)

    def test_real_pin_unchanged(self):
        self.assertEqual(PIN, "12d587dfb20741cafc376c42c696c5f6e2a64487")


class TestSyncOperatingContract(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sync-oc-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.root = self.tmp / "repo"
        (self.root / "references").mkdir(parents=True)
        self.canonical = self.root / "references" / "operating-contract.md"
        self.canonical.write_text("canonical words\n")
        for skill in ("alpha", "beta"):
            d = self.root / "skills" / skill / "references"
            d.mkdir(parents=True)
            (d / "operating-contract.md").write_text("canonical words\n")

    def run_sync(self, *flags):
        with mock.patch.object(sync_operating_contract, "REPO_ROOT", self.root):
            return sync_operating_contract.sync("--check" in flags)

    def test_check_passes_when_synchronized(self):
        self.assertEqual(self.run_sync("--check"), 0)

    def test_check_fails_on_drift(self):
        (self.root / "skills" / "beta" / "references" / "operating-contract.md").write_text(
            "drifted\n")
        self.assertEqual(self.run_sync("--check"), 1)

    def test_sync_repairs_drift(self):
        drifted = self.root / "skills" / "beta" / "references" / "operating-contract.md"
        drifted.write_text("drifted\n")
        self.assertEqual(self.run_sync(), 0)
        self.assertEqual(drifted.read_text(), "canonical words\n")
        self.assertEqual(self.run_sync("--check"), 0)

    def test_canonical_change_propagates(self):
        self.canonical.write_text("v2 words\n")
        self.assertEqual(self.run_sync("--check"), 1)
        self.assertEqual(self.run_sync(), 0)
        self.assertEqual(self.run_sync("--check"), 0)

    def test_real_repository_is_synchronized(self):
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "sync_operating_contract.py"),
             "--check"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
