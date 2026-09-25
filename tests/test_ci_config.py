"""Regression tests for CI configuration: pinned actions, exact deps, gates."""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "catalog-validation.yml"
REQS = REPO_ROOT / "requirements-ci.txt"

CHECKOUT_SHA = "11d5960a326750d5838078e36cf38b85af677262"
SETUP_PYTHON_SHA = "a26af69be951a213d495a4c3e4e4022e16d87065"


class TestWorkflowActions(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text()

    def test_actions_pinned_to_full_shas(self):
        uses = re.findall(r"uses:\s*(\S+)", self.text)
        self.assertTrue(uses)
        for action in uses:
            ref = action.split("@", 1)[1]
            self.assertRegex(ref, r"^[0-9a-f]{40}$", action)

    def test_checkout_sha_is_official_release(self):
        self.assertIn(f"actions/checkout@{CHECKOUT_SHA}", self.text)

    def test_setup_python_sha_is_official_release(self):
        self.assertIn(f"actions/setup-python@{SETUP_PYTHON_SHA}", self.text)

    def test_no_mutable_version_tags(self):
        for match in re.finditer(r"uses:\s*(\S+)", self.text):
            ref = match.group(1).split("@", 1)[1]
            self.assertFalse(ref.startswith("v"), match.group(1))


class TestWorkflowEvidence(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text()

    def test_head_job_checks_out_exact_pr_head(self):
        self.assertIn("ref: ${{ github.event.pull_request.head.sha }}", self.text)

    def test_head_job_proves_executed_equals_expected(self):
        head_idx = self.text.index("validate-head:")
        merge_idx = self.text.index("validate-merge:")
        head_section = self.text[head_idx:merge_idx]
        self.assertIn("--mode exact-head", head_section)

    def test_merge_job_proves_executed_differs_from_head(self):
        merge_idx = self.text.index("validate-merge:")
        main_idx = self.text.index("validate-main:")
        merge_section = self.text[merge_idx:main_idx]
        self.assertIn("--mode merge-result", merge_section)

    def test_push_job_does_not_reference_pull_request_event(self):
        main_idx = self.text.index("validate-main:")
        main_section = self.text[main_idx:]
        self.assertNotIn("github.event.pull_request", main_section)

    def test_both_pr_jobs_run_full_gates(self):
        for job in ("validate-head", "validate-merge"):
            idx = self.text.index(job + ":")
            section = self.text[idx:]
            for gate in ("validate_plugin_manifest.py", "validate_catalog.py",
                         "sync_operating_contract.py --check", "unittest discover",
                         "git diff --check"):
                self.assertIn(gate, section)


class TestDependencyPins(unittest.TestCase):
    def test_no_floating_constraints_in_workflow(self):
        text = WORKFLOW.read_text()
        self.assertNotIn("PyYAML>=", text)
        self.assertNotIn("jsonschema>=", text)
        self.assertIn("-r requirements-ci.txt", text)

    def test_requirements_exact_pins(self):
        for line in REQS.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            self.assertIn("==", line, line)
            self.assertNotIn(">=", line, line)
            self.assertNotIn("~=", line, line)


if __name__ == "__main__":
    unittest.main()
