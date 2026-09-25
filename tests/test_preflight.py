"""Behavior tests for preflight.py using temporary git repositories."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "preflight-repository" / "scripts"
sys.path.insert(0, str(REPO_SCRIPTS))
import preflight  # noqa: E402


def sh(cmd, cwd=None, env=None):
    proc = subprocess.run(cmd, cwd=cwd, env=env, shell=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed: {cmd}\n{proc.stderr}")
    return proc.stdout.strip()


class GitScenario:
    """Build a scratch repository scenario inside one temp directory."""

    def __init__(self):
        self.base = Path(tempfile.mkdtemp(prefix="preflight-test-"))
        self.addCleanup = None

    def repo(self, name, bare=False, initial_branch="main"):
        path = self.base / name
        if bare:
            path.mkdir(parents=True)
            sh(f"git init --bare -q -b {initial_branch} {name}", cwd=self.base)
        else:
            path.mkdir(parents=True)
            sh(f"git init -q -b {initial_branch} {name}", cwd=self.base)
            sh("git config user.email t@example.com && git config user.name t", cwd=path)
            sh("echo a > a.txt && git add a.txt && git commit -qm init", cwd=path)
        return path

    def cleanup(self):
        import shutil
        shutil.rmtree(self.base, ignore_errors=True)


class TestWorktreeClassification(unittest.TestCase):
    """Critical assertions: main is not linked merely because another
    worktree exists; linked is not submodule; classification uses git paths,
    not .git-file sniffing."""

    def setUp(self):
        self.sc = GitScenario()
        self.addCleanup(self.sc.cleanup)
        self.main = self.sc.repo("main-repo")

    def test_main_checkout_only(self):
        out = sh(f"python3 {REPO_SCRIPTS / 'preflight.py'} --repo {self.main} --json")
        facts = json.loads(out)
        self.assertEqual(facts["worktree"]["current_kind"], "main")
        self.assertFalse(facts["worktree"]["is_submodule"])

    def test_main_checkout_with_another_worktree_is_not_linked(self):
        linked = self.sc.base / "linked-wt"
        sh(f"git worktree add -q {linked} -b other-branch", cwd=self.main)
        out = sh(f"python3 {REPO_SCRIPTS / 'preflight.py'} --repo {self.main} --json")
        facts = json.loads(out)
        # Two worktrees exist, but THIS checkout is the main one.
        self.assertEqual(facts["worktree"]["current_kind"], "main")

    def test_current_checkout_is_linked_worktree_not_submodule(self):
        linked = self.sc.base / "linked-wt"
        sh(f"git worktree add -q {linked} -b other-branch", cwd=self.main)
        out = sh(f"python3 {REPO_SCRIPTS / 'preflight.py'} --repo {linked} --json")
        facts = json.loads(out)
        self.assertEqual(facts["worktree"]["current_kind"], "linked")
        self.assertFalse(facts["worktree"]["is_submodule"])

    def test_submodule_detected(self):
        child = self.sc.repo("child-repo")
        sh(f"git -c protocol.file.allow=always submodule add -q {child} child", cwd=self.main)
        sh("git -c protocol.file.allow=always submodule update -q --init", cwd=self.main)
        out = sh(f"python3 {REPO_SCRIPTS / 'preflight.py'} --repo {self.main / 'child'} --json")
        facts = json.loads(out)
        self.assertEqual(facts["worktree"]["current_kind"], "submodule")

    def test_detached_head(self):
        sh("git checkout -q --detach HEAD", cwd=self.main)
        out = sh(f"python3 {REPO_SCRIPTS / 'preflight.py'} --repo {self.main} --json")
        facts = json.loads(out)
        self.assertTrue(facts["branch"]["detached"])
        self.assertIsNone(facts["branch"]["current"])


class TestSyncParity(unittest.TestCase):
    """Critical assertion: local tracking parity does not masquerade as live
    remote parity."""

    def setUp(self):
        self.sc = GitScenario()
        self.addCleanup(self.sc.cleanup)
        remote = self.sc.repo("origin", bare=True)
        self.work = self.sc.repo("work")
        sh(f"git remote add origin {remote}", cwd=self.work)
        sh("git push -q -u origin main", cwd=self.work)

    def test_tracking_and_remote_both_match(self):
        out = sh(f"python3 {REPO_SCRIPTS / 'preflight.py'} --repo {self.work} --json")
        facts = json.loads(out)
        self.assertEqual(facts["sync"]["tracking_parity"], "yes")
        self.assertEqual(facts["sync"]["remote_parity"], "yes")

    def test_tracking_stale_while_live_remote_differs(self):
        # Remote advances; the local checkout does not. The local tracking
        # ref still matches HEAD, so tracking says yes while the live
        # remote says no: tracking parity is not remote truth.
        other = self.sc.repo("other-clone")
        sh(f"git remote add origin {self.sc.base / 'origin'}", cwd=other)
        sh("git push -q origin main", cwd=other)
        sh("echo b > b.txt && git add b.txt && git commit -qm advance", cwd=other)
        sh("git push -q origin main", cwd=other)
        out = sh(f"python3 {REPO_SCRIPTS / 'preflight.py'} --repo {self.work} --json")
        facts = json.loads(out)
        self.assertEqual(facts["sync"]["tracking_parity"], "yes")
        self.assertEqual(facts["sync"]["remote_parity"], "no")

    def test_tracking_parity_not_substituted_for_remote_parity(self):
        # Move only the LOCAL tracking ref to HEAD: tracking says yes while
        # the live remote says no.
        sh("git commit -q --allow-empty -m local-advance", cwd=self.work)
        head = sh("git rev-parse HEAD", cwd=self.work)
        sh(f"git update-ref refs/remotes/origin/main {head}", cwd=self.work)
        out = sh(f"python3 {REPO_SCRIPTS / 'preflight.py'} --repo {self.work} --json")
        facts = json.loads(out)
        self.assertEqual(facts["sync"]["tracking_parity"], "yes")
        self.assertEqual(facts["sync"]["remote_parity"], "no")

    def test_remote_branch_matches_head(self):
        out = sh(f"python3 {REPO_SCRIPTS / 'preflight.py'} --repo {self.work} --json")
        facts = json.loads(out)
        self.assertEqual(facts["sync"]["remote_branch_sha"],
                         facts["commit"]["head_sha"])

    def test_remote_unreachable_is_unknown(self):
        sh("git remote set-url origin /nonexistent/does-not-exist", cwd=self.work)
        out = sh(f"python3 {REPO_SCRIPTS / 'preflight.py'} --repo {self.work} --json")
        facts = json.loads(out)
        self.assertEqual(facts["sync"]["remote_parity"], "unknown")
        self.assertFalse(facts["sync"]["remote_reachable"])


class TestDefaultBranch(unittest.TestCase):
    def setUp(self):
        self.sc = GitScenario()
        self.addCleanup(self.sc.cleanup)

    def test_default_branch_main_from_remote(self):
        remote = self.sc.repo("origin", bare=True)
        work = self.sc.repo("work")
        sh(f"git remote add origin {remote}", cwd=work)
        sh("git push -q -u origin main", cwd=work)
        out = sh(f"python3 {REPO_SCRIPTS / 'preflight.py'} --repo {work} --json")
        facts = json.loads(out)
        self.assertEqual(facts["branch"]["default"], "main")
        self.assertEqual(facts["branch"]["default_source"], "remote_head_symref")

    def test_default_branch_non_main_trunk(self):
        remote = self.sc.repo("origin", bare=True, initial_branch="trunk")
        work = self.sc.repo("work", initial_branch="trunk")
        sh(f"git remote add origin {remote}", cwd=work)
        sh("git push -q -u origin trunk", cwd=work)
        out = sh(f"python3 {REPO_SCRIPTS / 'preflight.py'} --repo {work} --json")
        facts = json.loads(out)
        self.assertEqual(facts["branch"]["default"], "trunk")
        self.assertEqual(facts["branch"]["default_source"], "remote_head_symref")

    def test_explicit_override_wins(self):
        remote = self.sc.repo("origin", bare=True)
        work = self.sc.repo("work")
        sh(f"git remote add origin {remote}", cwd=work)
        sh("git push -q -u origin main", cwd=work)
        out = sh(f"python3 {REPO_SCRIPTS / 'preflight.py'} --repo {work} "
                 "--default-branch trunk --json")
        facts = json.loads(out)
        self.assertEqual(facts["branch"]["default"], "trunk")
        self.assertEqual(facts["branch"]["default_source"], "explicit_override")


class TestTreeState(unittest.TestCase):
    def setUp(self):
        self.sc = GitScenario()
        self.addCleanup(self.sc.cleanup)
        self.work = self.sc.repo("work")

    def test_clean_tree(self):
        out = sh(f"python3 {REPO_SCRIPTS / 'preflight.py'} --repo {self.work} --json")
        facts = json.loads(out)
        self.assertTrue(facts["tree"]["clean"])

    def test_dirty_tree(self):
        sh("echo dirty > dirty.txt", cwd=self.work)
        out = sh(f"python3 {REPO_SCRIPTS / 'preflight.py'} --repo {self.work} --json")
        facts = json.loads(out)
        self.assertFalse(facts["tree"]["clean"])
        self.assertGreaterEqual(facts["tree"]["untracked"], 1)

    def test_status_failure_reports_unknown_and_not_ready(self):
        tracked = self.work / "a.txt"
        tracked.write_text("modified before index corruption\n")
        index = self.work / ".git" / "index"
        index.write_bytes(b"corrupt index")
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.work,
                                capture_output=True, text=True)
        self.assertNotEqual(status.returncode, 0, status.stdout + status.stderr)
        proc = subprocess.run(
            [sys.executable, str(REPO_SCRIPTS / "preflight.py"), "--repo", str(self.work),
             "--default-branch", "main", "--json"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        facts = json.loads(proc.stdout)
        self.assertIsNone(facts["tree"]["clean"])
        self.assertEqual(facts["tree"]["state"], "UNKNOWN")
        self.assertTrue(facts["tree"]["error"])
        self.assertIsNone(facts["verdict_inputs"]["tree_clean"])
        self.assertEqual(facts["verdict_inputs"]["tree_status"], "UNKNOWN")
        self.assertNotEqual("READY", facts["verdict_inputs"].get("verdict"))


if __name__ == "__main__":
    unittest.main()
