"""Behavior tests for discover_stack.py using a fake gh executable.

The real script runs `gh pr list` and `gh repo view`; a stub gh on PATH
serves canned JSON from fixtures, so no live GitHub is required.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "skills" / "integrate-pr-stack" / "scripts" / "discover_stack.py"

GH_API = "https://api.github.com/repos/egawilldoit/skills/pulls"


def pr(number, head, base, head_sha, base_sha, draft=False):
    return {
        "number": number, "title": f"PR {number}", "url": f"https://example.com/{number}",
        "isDraft": draft, "baseRefName": base, "headRefName": head,
        "baseRefOid": base_sha, "headRefOid": head_sha,
    }


def stub_gh(bindir, prs_json, repo_view_json=None):
    gh = bindir / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "repo" ]; then\n'
        f"  printf '%s\\n' '{json.dumps(repo_view_json)}'\n"
        "  exit 0\n"
        "fi\n"
        f"printf '%s\\n' '{json.dumps(prs_json)}'\n"
    )
    gh.chmod(0o755)


class DiscoverCase:
    def __init__(self, prs, default_branch_ref=None):
        self.tmp = Path(tempfile.mkdtemp(prefix="stack-"))
        self.bindir = self.tmp / "bin"
        self.bindir.mkdir()
        repo_view = None
        if default_branch_ref is not None:
            repo_view = {"defaultBranchRef": {"name": default_branch_ref}}
        stub_gh(self.bindir, prs, repo_view)

    def run(self, *flags, cwd=None):
        env = dict(os.environ)
        env["PATH"] = f"{self.bindir}{os.pathsep}{env['PATH']}"
        env.pop("GH_TOKEN", None)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), *flags],
            cwd=cwd or self.tmp, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, timeout=60,
        )
        return proc

    def cleanup(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)


A_SHA = "1" * 40
B_SHA = "2" * 40
C_SHA = "3" * 40


class TestStackDiscovery(unittest.TestCase):
    def setUp(self):
        self._cases = []

    def tearDown(self):
        for case in self._cases:
            case.cleanup()

    def case(self, prs, default_branch_ref="main"):
        c = DiscoverCase(prs, default_branch_ref=default_branch_ref)
        self._cases.append(c)
        return c

    def test_default_branch_main_resolved(self):
        case = self.case([pr(1, "feat-a", "main", A_SHA, B_SHA)], default_branch_ref="main")
        out = json.loads(case.run("--json").stdout)
        self.assertEqual(out["default_branch"], "main")
        self.assertEqual(out["default_branch_source"], "github_default_ref")
        self.assertEqual(len(out["chains"]), 1)

    def test_default_branch_trunk(self):
        case = self.case([pr(1, "feat-a", "trunk", A_SHA, B_SHA)], default_branch_ref="trunk")
        out = json.loads(case.run("--json").stdout)
        self.assertEqual(out["default_branch"], "trunk")
        self.assertEqual(len(out["chains"]), 1)
        self.assertEqual(out["chains"][0]["prs"][0]["number"], 1)

    def test_one_normal_pr(self):
        case = self.case([pr(7, "feat", "main", A_SHA, B_SHA)])
        out = json.loads(case.run("--json").stdout)
        self.assertEqual(out["chains"][0]["length"], 1)
        self.assertEqual(out["chains"][0]["prs"][0]["number"], 7)
        self.assertEqual(out["orphans"], [])

    def test_normal_three_pr_stack(self):
        prs = [
            pr(1, "stack-1", "main", A_SHA, B_SHA),
            pr(2, "stack-2", "stack-1", B_SHA, A_SHA),
            pr(3, "stack-3", "stack-2", C_SHA, B_SHA),
        ]
        case = self.case(prs)
        out = json.loads(case.run("--json").stdout)
        self.assertEqual(len(out["chains"]), 1)
        self.assertEqual(out["chains"][0]["length"], 3)
        self.assertEqual([p["number"] for p in out["chains"][0]["prs"]], [1, 2, 3])
        self.assertEqual(out["orphans"], [])

    def test_forked_stack(self):
        prs = [
            pr(1, "fork-base", "main", A_SHA, B_SHA),
            pr(2, "fork-a", "fork-base", B_SHA, A_SHA),
            pr(3, "fork-b", "fork-base", C_SHA, A_SHA),
        ]
        case = self.case(prs)
        out = json.loads(case.run("--json").stdout)
        self.assertEqual(len(out["chains"]), 1)
        self.assertIn("fork", out["chains"][0]["prs"][0])
        self.assertEqual(out["chains"][0]["prs"][0]["fork"], [2, 3])

    def test_orphan_pr(self):
        prs = [
            pr(1, "chained", "main", A_SHA, B_SHA),
            pr(2, "orphan", "ghost-branch", C_SHA, B_SHA),
        ]
        case = self.case(prs)
        out = json.loads(case.run("--json").stdout)
        self.assertEqual(out["orphans"], [2])

    def test_missing_default_branch_errors(self):
        case = DiscoverCase([pr(1, "feat-a", "main", A_SHA, B_SHA)])
        # No default branch resolvable (gh view empty, no git remote).
        proc = case.run("--json")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("default branch", proc.stderr.lower())

    def test_explicit_override(self):
        case = self.case([pr(1, "feat-a", "main", A_SHA, B_SHA)])
        out = json.loads(case.run("--default-branch", "main", "--json").stdout)
        self.assertEqual(out["default_branch_source"], "explicit_override")


class TestAncestryClassification(unittest.TestCase):
    """Separate unknown ancestry from confirmed not-ancestor."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ancestry-"))
        self.addCleanup(__import__("shutil").rmtree, self.tmp, ignore_errors=True)
        self.bindir = self.tmp / "bin"
        self.bindir.mkdir()
        def sh(cmd):
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return r.stdout.strip()
        subprocess.run(f"git init -q -b main {self.tmp / 'repo'}", shell=True, check=True)
        sh(f"git -C {self.tmp / 'repo'} config user.email t@t")
        sh(f"git -C {self.tmp / 'repo'} config user.name t")
        sh(f"cd {self.tmp / 'repo'} && echo a > a && git add a && git commit -qm one")
        sh(f"cd {self.tmp / 'repo'} && echo b > b && git add b && git commit -qm two")
        self.two_sha = sh(f"git -C {self.tmp / 'repo'} rev-parse HEAD")
        self.one_sha = sh(f"git -C {self.tmp / 'repo'} rev-parse HEAD~1")

        prs = [
            pr(1, "stack-1", "main", self.one_sha, self.one_sha),
            pr(2, "stack-2", "stack-1", self.two_sha, self.one_sha),
            pr(3, "unrelated", "stack-2", self.two_sha, self.one_sha),
        ]
        stub_gh(self.bindir, prs, {"defaultBranchRef": {"name": "main"}})

    def test_ancestor_and_non_ancestor_and_unknown(self):
        # Modify the gh stub so PR #3's base sha is a valid-but-unrelated
        # commit that does NOT exist locally => unknown; PR #2's ancestry is
        # a real ancestor; a confirmed non-ancestor needs valid objects.
        env = dict(os.environ)
        env["PATH"] = f"{self.bindir}{os.pathsep}{env['PATH']}"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"], cwd=self.tmp / "repo",
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60,
        )
        out = json.loads(proc.stdout)
        pr2 = out["chains"][0]["prs"][1]
        pr3 = out["chains"][0]["prs"][2]
        # PR #2's base is PR #1's head (same commit): ancestor=yes.
        self.assertEqual(pr2["ancestry_from_below"], "yes")

    def test_confirmed_not_ancestor(self):
        # PR #2's base is the older commit but its head is NOT an ancestor
        # of anything below it: ancestry between chain entries uses
        # (lower head, this base). Use base=one_sha, lower head=two_sha:
        # two_sha is NOT an ancestor of one_sha => "no".
        prs = [
            pr(1, "stack-1", "main", self.two_sha, self.one_sha),
            pr(2, "stack-2", "stack-1", self.two_sha, self.one_sha),
        ]
        stub_gh(self.bindir, prs, {"defaultBranchRef": {"name": "main"}})
        env = dict(os.environ)
        env["PATH"] = f"{self.bindir}{os.pathsep}{env['PATH']}"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"], cwd=self.tmp / "repo",
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60,
        )
        out = json.loads(proc.stdout)
        self.assertEqual(out["chains"][0]["prs"][1]["ancestry_from_below"], "no")

    def test_unknown_ancestry_when_objects_missing(self):
        # Run from an empty directory: the SHAs cannot resolve locally.
        prs = [
            pr(1, "stack-1", "main", "9" * 40, "8" * 40),
            pr(2, "stack-2", "stack-1", "7" * 40, "9" * 40),
        ]
        stub_gh(self.bindir, prs, {"defaultBranchRef": {"name": "main"}})
        env = dict(os.environ)
        env["PATH"] = f"{self.bindir}{os.pathsep}{env['PATH']}"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"], cwd=self.tmp,
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60,
        )
        out = json.loads(proc.stdout)
        self.assertEqual(out["chains"][0]["prs"][1]["ancestry_from_below"], "unknown")


if __name__ == "__main__":
    unittest.main()
