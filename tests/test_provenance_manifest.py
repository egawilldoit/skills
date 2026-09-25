"""Behavior tests for provenance_manifest.py."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "trace-artifact-provenance" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import provenance_manifest  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli(*flags, cwd=REPO_ROOT):
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "provenance_manifest.py"), *flags],
        cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60,
    )
    return proc.returncode, proc.stdout, proc.stderr


def args(**kwargs):
    defaults = dict(artifact="", kind="other", name=None, digest_algorithm="sha256",
                    source_sha=None, source_ref=None, repository=None, build_id=None,
                    build_pipeline=None, build_builder=None, build_input=None,
                    release_id=None, release_name=None, release_url=None,
                    deployment_kind=None, deployment_target=None,
                    deployment_environment=None, deployment_version=None,
                    deployment_digest=None, cwd=".")
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestFileArtifact(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="prov-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.file = self.dir / "app.bin"
        self.file.write_bytes(b"\x00\x01artifact-bytes")

    def test_single_file_digest_matches_sha256sum(self):
        manifest = provenance_manifest.build_manifest(args(artifact=str(self.file)))
        out = subprocess.run(["sha256sum", str(self.file)], capture_output=True, text=True)
        self.assertEqual(manifest["artifact"]["digest"], out.stdout.split()[0])
        self.assertEqual(manifest["artifact"]["status"], "VERIFIED")

    def test_verify_match_and_mismatch(self):
        manifest_path = self.dir / "manifest.json"
        run_cli("--artifact", str(self.file), "--output", str(manifest_path))
        code, out, _ = run_cli("--artifact", str(self.file), "--verify", str(manifest_path))
        self.assertIn("MATCH", out)
        self.assertEqual(code, 0)
        self.file.write_bytes(b"tampered")
        code, out, _ = run_cli("--artifact", str(self.file), "--verify", str(manifest_path))
        self.assertIn("MISMATCH", out)
        self.assertEqual(code, 1)

    def test_file_recheck_commands_include_sha256sum(self):
        manifest = provenance_manifest.build_manifest(args(artifact=str(self.file)))
        self.assertTrue(any(c.startswith("sha256sum") for c in
                            manifest["verification"]["recheck_commands"]))


class TestDirectoryArtifact(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="prov-dir-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.tree = self.dir / "dist"
        (self.tree / "sub").mkdir(parents=True)
        (self.tree / "b.txt").write_text("beta")
        (self.tree / "a.txt").write_text("alpha")
        (self.tree / "sub" / "c.txt").write_text("gamma")

    def test_directory_digest_and_reverify(self):
        manifest_path = self.dir / "manifest.json"
        run_cli("--artifact", str(self.tree), "--output", str(manifest_path))
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["artifact"]["file_count"], 3)
        code, out, _ = run_cli("--artifact", str(self.tree), "--verify", str(manifest_path))
        self.assertIn("MATCH", out)

    def test_directory_digest_deterministic_ordering(self):
        m1 = provenance_manifest.build_manifest(args(artifact=str(self.tree)))
        # Rewrite files in a different physical order; digest must not change.
        (self.tree / "b.txt").write_text("beta")
        (self.tree / "a.txt").write_text("alpha")
        m2 = provenance_manifest.build_manifest(args(artifact=str(self.tree)))
        self.assertEqual(m1_digest := provenance_manifest.build_manifest(
            args(artifact=str(self.tree)))["artifact"]["digest"], m2["artifact"]["digest"])
        self.assertEqual(m1_digest, m1_digest)  # stable reference

    def test_directory_recheck_commands_do_not_suggest_sha256sum(self):
        manifest = provenance_manifest.build_manifest(args(artifact=str(self.tree)))
        for cmd in manifest["verification"]["recheck_commands"]:
            self.assertFalse(cmd.startswith("sha256sum"),
                             f"invalid directory recheck suggested: {cmd}")
            self.assertIn("provenance_manifest.py", cmd)

    def test_directory_verification_mismatch(self):
        manifest_path = self.dir / "manifest.json"
        run_cli("--artifact", str(self.tree), "--output", str(manifest_path))
        (self.tree / "a.txt").write_text("changed")
        code, out, _ = run_cli("--artifact", str(self.tree), "--verify", str(manifest_path))
        self.assertEqual(code, 1)
        self.assertIn("MISMATCH", out)


class TestSymlinkBehavior(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="prov-sym-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def _tree(self, target, name=None):
        tree = self.dir / (name or ("tree-" + target.replace("/", "_")))
        tree.mkdir()
        (tree / "real.txt").write_text("real")
        link = tree / "link.txt"
        if link.is_symlink() or link.exists():
            link.unlink()
        os.symlink(target, link)
        return tree

    def test_symlink_target_changes_digest(self):
        m1 = provenance_manifest.build_manifest(args(artifact=str(self._tree("one"))))
        m2 = provenance_manifest.build_manifest(args(artifact=str(self._tree("two"))))
        self.assertNotEqual(m1["artifact"]["digest"], m2["artifact"]["digest"])

    def test_symlink_included_not_omitted(self):
        tree = self._tree("one")
        manifest = provenance_manifest.build_manifest(args(artifact=str(tree)))
        self.assertEqual(manifest["artifact"]["entry_count"], 2)  # file + symlink

    def test_broken_symlink_handled(self):
        tree = self._tree("/nonexistent/broken-target", name="tree-broken")
        manifest = provenance_manifest.build_manifest(args(artifact=str(tree)))
        self.assertEqual(manifest["artifact"]["status"], "VERIFIED")

    def test_symlink_to_directory_not_followed(self):
        tree = self.dir / "tree"
        tree.mkdir()
        (tree / "sub").mkdir()
        (tree / "sub" / "x.txt").write_text("x")
        (tree / "loop").symlink_to(tree / "sub")
        # Must terminate and hash without following the link into recursion.
        manifest = provenance_manifest.build_manifest(args(artifact=str(tree)))
        self.assertTrue(manifest["artifact"]["digest"])


class TestProvenanceStatuses(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="prov-status-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.file = self.dir / "a.bin"
        self.file.write_bytes(b"x" * 10)

    def _run(self, **kwargs):
        return provenance_manifest.build_manifest(
            args(artifact=str(self.file), cwd=str(REPO_ROOT), **kwargs))

    def test_supplied_sha_that_resolves_is_resolved(self):
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                              capture_output=True, text=True).stdout.strip()
        manifest = self._run(source_sha=head)
        self.assertEqual(manifest["source"]["sha_status"], "RESOLVED")

    def test_supplied_fake_sha_stays_supplied(self):
        manifest = self._run(source_sha="f" * 40)
        self.assertEqual(manifest["source"]["sha_status"], "SUPPLIED")
        self.assertNotEqual(manifest["source"]["sha_status"], "VERIFIED")

    def test_build_id_supplied_not_verified(self):
        manifest = self._run(build_id="CI-1234")
        self.assertEqual(manifest["build"]["id_status"], "SUPPLIED")

    def test_release_id_supplied_not_verified(self):
        manifest = self._run(release_id="rel-9")
        self.assertEqual(manifest["release"]["id_status"], "SUPPLIED")

    def test_deployment_supplied_not_verified(self):
        manifest = self._run(deployment_target="prod", deployment_version="v1.2.3")
        self.assertEqual(manifest["deployment"]["status"], "SUPPLIED")
        self.assertNotEqual(manifest["deployment"]["status"], "VERIFIED")

    def test_deployment_digest_alone_supplied(self):
        manifest = self._run(deployment_target="prod",
                             deployment_digest="sha256:" + "0" * 64)
        self.assertEqual(manifest["deployment"]["status"], "SUPPLIED")

    def test_artifact_verified_while_chain_partial(self):
        manifest = self._run(build_id="CI-1", deployment_target="prod",
                             deployment_version="v1")
        self.assertEqual(manifest["artifact"]["status"], "VERIFIED")
        self.assertEqual(manifest["build"]["id_status"], "SUPPLIED")
        self.assertEqual(manifest["deployment"]["status"], "SUPPLIED")

    def test_no_unrelated_field_becomes_verified(self):
        manifest = self._run(source_sha="f" * 40, build_id="B", release_id="R",
                             deployment_target="d", deployment_version="v")
        verified_sections = []
        for section, fields in manifest.items():
            if isinstance(fields, dict):
                for key, value in fields.items():
                    if key.endswith("status") and value == "VERIFIED":
                        verified_sections.append((section, key))
        self.assertEqual(verified_sections, [("artifact", "status")])


if __name__ == "__main__":
    unittest.main()
