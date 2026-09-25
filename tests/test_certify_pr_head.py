"""Behavior tests for certify_pr_head.py.

Run the real script via subprocess and assert exact semantic verdicts.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "skills" / "certify-pr-head" / "scripts" / "certify_pr_head.py"

HEAD = "a" * 40
OLD = "b" * 40
MERGE = "c" * 40


def run_certify(*flags):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--head", HEAD, "--cwd", str(REPO_ROOT), "--json", *flags],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"certify failed: {proc.stderr}")
    return json.loads(proc.stdout)


def evidence(**kwargs):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(kwargs, fh)
        return fh.name


class TestVerdicts(unittest.TestCase):
    def test_exact_everything_certified(self):
        out = run_certify("--reviewed", HEAD, "--tested", HEAD, "--ci-associated-head", HEAD,
                          "--ci-executed-sha", HEAD, "--ci-conclusion", "success")
        self.assertEqual(out["verdict"], "EXACT_HEAD_CERTIFIED")
        self.assertEqual(out["ci_execution_mode"], "HEAD")
        self.assertEqual(out["ci_associated_head_sha"], HEAD)
        self.assertEqual(out["ci_executed_sha"], HEAD)
        self.assertEqual(out["ci_conclusion"], "success")

    def test_stale_reviewed_sha(self):
        out = run_certify("--reviewed", OLD, "--tested", HEAD, "--ci-associated-head", HEAD,
                          "--ci-executed-sha", HEAD, "--ci-conclusion", "success")
        self.assertEqual(out["verdict"], "STALE_EVIDENCE")

    def test_stale_tested_sha(self):
        out = run_certify("--reviewed", HEAD, "--tested", OLD, "--ci-associated-head", HEAD,
                          "--ci-executed-sha", HEAD, "--ci-conclusion", "success")
        self.assertEqual(out["verdict"], "STALE_EVIDENCE")

    def test_head_moved_after_evidence(self):
        path = evidence(head=OLD, reviewed=OLD, tested=OLD,
                        ci={"associated_head_sha": OLD, "executed_sha": OLD,
                            "conclusion": "success"})
        out = run_certify("--evidence", path, "--evidence-head", OLD)
        self.assertEqual(out["verdict"], "HEAD_MOVED")

    def test_synthetic_merge_sha_is_not_exact_head_certified(self):
        # The defect discovered on this PR: CI associated with the head but
        # executed a synthetic merge commit. This must NOT certify.
        out = run_certify("--reviewed", HEAD, "--tested", HEAD,
                          "--ci-associated-head", HEAD, "--ci-executed-sha", MERGE,
                          "--ci-conclusion", "success")
        self.assertEqual(out["verdict"], "INCOMPLETE")
        self.assertEqual(out["ci_execution_mode"], "MERGE_RESULT")
        self.assertIn("differs from the reference head", out["reason"].lower())
        self.assertNotEqual(out["verdict"], "EXACT_HEAD_CERTIFIED")

    def test_legacy_ci_sha_without_executed_is_incomplete(self):
        out = run_certify("--reviewed", HEAD, "--tested", HEAD, "--ci", HEAD)
        self.assertEqual(out["verdict"], "INCOMPLETE")
        self.assertEqual(out["ci_execution_mode"], "UNKNOWN")

    def test_missing_executed_sha(self):
        out = run_certify("--reviewed", HEAD, "--tested", HEAD, "--ci-associated-head", HEAD,
                          "--ci-conclusion", "success")
        self.assertEqual(out["verdict"], "INCOMPLETE")

    def test_ci_conclusion_failure(self):
        out = run_certify("--reviewed", HEAD, "--tested", HEAD, "--ci-associated-head", HEAD,
                          "--ci-executed-sha", HEAD, "--ci-conclusion", "failure")
        self.assertEqual(out["verdict"], "INCOMPLETE")
        self.assertIn("failure", out["reason"])

    def test_mixed_stale_evidence(self):
        out = run_certify("--reviewed", OLD, "--tested", OLD, "--ci-associated-head", OLD,
                          "--ci-executed-sha", OLD, "--ci-conclusion", "success")
        self.assertEqual(out["verdict"], "STALE_EVIDENCE")

    def test_abbreviated_unresolvable_sha_is_missing(self):
        out = run_certify("--reviewed", HEAD, "--tested", "ffffff", "--ci-associated-head", HEAD,
                          "--ci-executed-sha", HEAD, "--ci-conclusion", "success")
        self.assertEqual(out["verdict"], "INCOMPLETE")
        self.assertEqual(out["evidence"]["tested"]["status"], "missing")

    def test_abbreviated_resolvable_sha_expands(self):
        # Build a self-contained temp repo so the abbreviation does not
        # depend on this repository's history being non-shallow.
        import subprocess as sp
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, tmp, ignore_errors=True)
        sp.run(f"git init -q -b main {tmp / 'repo'}", shell=True, check=True)
        sp.run(f"git -C {tmp / 'repo'} config user.email t@t && "
               f"git -C {tmp / 'repo'} config user.name t", shell=True, check=True)
        sp.run(f"cd {tmp / 'repo'} && echo a > a && git add a && git commit -qm one && "
               "echo b > b && git add b && git commit -qm two", shell=True, check=True)
        old = sp.run(f"git -C {tmp / 'repo'} rev-parse HEAD~1",
                     shell=True, capture_output=True, text=True).stdout.strip()
        abbrev = old[:8]
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--head", HEAD, "--cwd", str(tmp / "repo"),
             "--json", "--reviewed", abbrev, "--tested", HEAD,
             "--ci-associated-head", HEAD, "--ci-executed-sha", HEAD,
             "--ci-conclusion", "success"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["evidence"]["reviewed"]["sha"], old)
        self.assertEqual(out["verdict"], "STALE_EVIDENCE")

    def test_merge_result_with_all_exact_reviewed_tested_still_incomplete(self):
        # Even with reviewed+tested at head, exact-head certification
        # requires CI executed on the exact head.
        out = run_certify("--reviewed", HEAD, "--tested", HEAD,
                          "--ci-associated-head", HEAD, "--ci-executed-sha", MERGE,
                          "--ci-conclusion", "success")
        self.assertEqual(out["verdict"], "INCOMPLETE")

    def test_no_evidence_incomplete(self):
        out = run_certify()
        self.assertEqual(out["verdict"], "INCOMPLETE")

    def test_evidence_file_accepts_sha_objects(self):
        path = evidence(head=HEAD, reviewed={"sha": HEAD}, tested={"sha": HEAD},
                        ci={"associated_head_sha": HEAD, "executed_sha": HEAD,
                            "conclusion": "success"})
        out = run_certify("--evidence", path)
        self.assertEqual(out["verdict"], "EXACT_HEAD_CERTIFIED")
        self.assertEqual(out["ci_execution_mode"], "HEAD")


if __name__ == "__main__":
    unittest.main()
