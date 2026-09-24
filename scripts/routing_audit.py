#!/usr/bin/env python3
"""Routing audit: surface description overlap across skill clusters.

The description decides activation, so near-identical wording between sibling
skills is a routing bug. This script groups skills into the clusters that are
most at risk of collision, prints their descriptions, and flags pairs whose
descriptions share too many significant words.

It reports; it does not edit. A human or the authoring model resolves a flag.

Usage:
    python3 scripts/routing_audit.py [--threshold 0.45]
"""

from __future__ import annotations

import argparse
import re
import sys
from itertools import combinations
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)

STOPWORDS = {
    "a", "an", "the", "and", "or", "to", "of", "for", "in", "on", "at", "by",
    "with", "is", "are", "be", "it", "its", "this", "that", "these", "those",
    "as", "when", "use", "used", "using", "into", "from", "before", "after",
    "not", "but", "if", "so", "than", "then", "them", "they", "their", "there",
    "you", "your", "we", "our", "i", "do", "does", "done", "can", "will",
    "skill", "skills", "one", "two", "all", "any", "each", "more", "most",
}

CLUSTERS: dict[str, list[str]] = {
    "verification": [
        "verify-this", "verify-ui", "verify-cli", "certify-pr-head",
        "certify-release", "certify-production-target", "certify-database-rollout",
        "certify-mcp-production", "trace-artifact-provenance",
    ],
    "review": [
        "blast-radius", "adversarial-review", "review-and-ship",
        "make-pr-easy-to-review",
    ],
    "understanding_design": [
        "understand-codebase", "recover-design-rationale", "design-architecture",
        "compare-designs",
    ],
    "context_learning": [
        "recover-work-context", "work-retrospective", "mine-work-patterns",
        "what-did-i-get-done", "weekly-review",
    ],
    "pr_ci": [
        "review-and-ship", "loop-on-ci", "fix-ci", "get-pr-comments",
        "fix-merge-conflicts", "new-branch-and-pr", "integrate-pr-stack",
        "make-pr-easy-to-review",
    ],
    "repo_state": [
        "preflight-repository", "reconcile-project-truth", "recover-work-context",
        "record-evidence", "build-execution-contract",
    ],
    "verification_harness": [
        "create-verification-workflow", "maintain-verification-workflow",
        "run-smoke-tests", "verify-ui", "verify-cli",
    ],
}


def load_description(name: str) -> str:
    text = (SKILLS_DIR / name / "SKILL.md").read_text()
    match = FRONTMATTER_RE.match(text)
    if not match:
        return ""
    return str(yaml.safe_load(match.group(1)).get("description", ""))


def tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.45)
    args = parser.parse_args()

    descriptions = {p.name: load_description(p.name) for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file()}

    flags = 0
    for cluster, members in CLUSTERS.items():
        present = [m for m in members if m in descriptions]
        print(f"\n## {cluster}")
        for name in present:
            print(f"\n- {name}\n  {descriptions[name]}")
        for a, b in combinations(present, 2):
            ta, tb = tokens(descriptions[a]), tokens(descriptions[b])
            if not ta or not tb:
                continue
            jaccard = len(ta & tb) / len(ta | tb)
            if jaccard >= args.threshold:
                flags += 1
                shared = ", ".join(sorted(ta & tb))
                print(f"\n  [FLAG] {a} <-> {b}: overlap {jaccard:.2f} ({shared})")

    print(f"\n{flags} overlap flag(s) at threshold {args.threshold}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
