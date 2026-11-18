"""Routing-audit tests for the first-skill no-neighbor sentinel."""

import importlib.util
import json
import sys
import tempfile
from unittest import mock
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "trigger_audit.py"


def load_module():
    spec = importlib.util.spec_from_file_location("trigger_audit", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def base_case(skill, negative_expected=None, collision_expected=None):
    return {
        "skill": skill,
        "direct": f"Review the {skill} evidence for correctness",
        "indirect": f"Check the {skill} output before continuing",
        "incomplete": f"Review {skill}",
        "negative": "Summarize quarterly revenue in a board report",
        "negative_expected": negative_expected,
        "collision": "Prepare a financial forecast for next quarter",
        "collision_expected": collision_expected,
        "edge": f"Review {skill} with incomplete evidence",
    }


class TriggerAuditNeighborTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "skills").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "upstream-sources.json").write_text(
            json.dumps({"sources": [{"skill": "first-skill", "mode": "original"}]})
        )
        (self.root / "skills" / "first-skill").mkdir()
        (self.root / "skills" / "first-skill" / "SKILL.md").write_text(
            "---\nname: first-skill\ndescription: Review a first skill for clear evidence.\n---\n\n# First\n"
        )
        self.module = load_module()
        self.module.REPO_ROOT = self.root
        self.module.SKILLS_DIR = self.root / "skills"
        self.module.CASES = self.root / "tests" / "trigger-cases.json"

    def tearDown(self):
        self.tmp.cleanup()

    def write_cases(self, cases):
        self.module.CASES.write_text(json.dumps(cases))

    def run_main(self):
        with mock.patch.object(sys, "argv", ["trigger_audit.py"]):
            return self.module.main()

    def test_first_skill_with_null_neighbors_passes(self):
        self.write_cases([base_case("first-skill")])
        self.assertEqual(self.run_main(), 0)

    def test_null_neighbors_remain_valid_after_second_skill(self):
        (self.root / "skills" / "second-skill").mkdir()
        (self.root / "skills" / "second-skill" / "SKILL.md").write_text(
            "---\nname: second-skill\ndescription: Audit a second skill for unusual risks.\n---\n\n# Second\n"
        )
        sources = json.loads((self.root / "upstream-sources.json").read_text())
        sources["sources"].append({"skill": "second-skill", "mode": "original"})
        (self.root / "upstream-sources.json").write_text(json.dumps(sources))
        self.write_cases([
            base_case("first-skill"),
            base_case("second-skill", "first-skill", "first-skill"),
        ])
        self.assertEqual(self.run_main(), 0)

    def test_unknown_named_neighbor_fails(self):
        case = base_case("first-skill", "does-not-exist", "does-not-exist")
        self.write_cases([case])
        self.assertEqual(self.run_main(), 1)

    def test_null_neighbor_with_target_describing_example_fails(self):
        case = base_case("first-skill")
        case["negative"] = "Review first skill evidence for correctness"
        self.write_cases([case])
        self.assertEqual(self.run_main(), 1)

    def test_null_neighbor_with_too_few_words_fails(self):
        case = base_case("first-skill")
        case["collision"] = "other"
        self.write_cases([case])
        self.assertEqual(self.run_main(), 1)


if __name__ == "__main__":
    unittest.main()
