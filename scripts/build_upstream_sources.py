#!/usr/bin/env python3
"""Build upstream-sources.json from the pinned Cursor source.

Every imported or adapted skill records its source path, the single pinned
source commit, its license, and its import mode. Original skills record mode
only. Output is sorted deterministically.

Usage:
    python3 scripts/build_upstream_sources.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "upstream-sources.json"

SOURCE_REPOSITORY = "https://github.com/cursor/plugins"
SOURCE_COMMIT = "12d587dfb20741cafc376c42c696c5f6e2a64487"
LICENSE = "MIT"

PSTACK = "pstack/skills"
TEAM_KIT = "cursor-team-kit/skills"

COPIED: dict[str, str] = {
    "blast-radius": f"{PSTACK}/blast-radius",
    "tdd": f"{PSTACK}/tdd",
    "technical-writing": f"{PSTACK}/technical-writing",
    "typescript-best-practices": f"{PSTACK}/typescript-best-practices",
    "unslop": f"{PSTACK}/unslop",
    "principle-attack-the-premise": f"{PSTACK}/principle-attack-the-premise",
    "principle-boundary-discipline": f"{PSTACK}/principle-boundary-discipline",
    "principle-build-the-lever": f"{PSTACK}/principle-build-the-lever",
    "principle-encode-lessons-in-structure": f"{PSTACK}/principle-encode-lessons-in-structure",
    "principle-exhaust-the-design-space": f"{PSTACK}/principle-exhaust-the-design-space",
    "principle-experience-first": f"{PSTACK}/principle-experience-first",
    "principle-fix-root-causes": f"{PSTACK}/principle-fix-root-causes",
    "principle-foundational-thinking": f"{PSTACK}/principle-foundational-thinking",
    "principle-guard-the-context-window": f"{PSTACK}/principle-guard-the-context-window",
    "principle-laziness-protocol": f"{PSTACK}/principle-laziness-protocol",
    "principle-make-operations-idempotent": f"{PSTACK}/principle-make-operations-idempotent",
    "principle-migrate-callers-then-delete-legacy-apis": f"{PSTACK}/principle-migrate-callers-then-delete-legacy-apis",
    "principle-minimize-reader-load": f"{PSTACK}/principle-minimize-reader-load",
    "principle-model-the-domain": f"{PSTACK}/principle-model-the-domain",
    "principle-outcome-oriented-execution": f"{PSTACK}/principle-outcome-oriented-execution",
    "principle-prove-it-works": f"{PSTACK}/principle-prove-it-works",
    "principle-redesign-from-first-principles": f"{PSTACK}/principle-redesign-from-first-principles",
    "principle-separate-before-serializing-shared-state": f"{PSTACK}/principle-separate-before-serializing-shared-state",
    "principle-sequence-verifiable-units": f"{PSTACK}/principle-sequence-verifiable-units",
    "principle-subtract-before-you-add": f"{PSTACK}/principle-subtract-before-you-add",
    "principle-test-behavior-not-implementation": f"{PSTACK}/principle-test-behavior-not-implementation",
    "principle-type-system-discipline": f"{PSTACK}/principle-type-system-discipline",
    "verify-this": f"{TEAM_KIT}/verify-this",
    "review-and-ship": f"{TEAM_KIT}/review-and-ship",
    "make-pr-easy-to-review": f"{TEAM_KIT}/make-pr-easy-to-review",
    "loop-on-ci": f"{TEAM_KIT}/loop-on-ci",
    "fix-ci": f"{TEAM_KIT}/fix-ci",
    "run-smoke-tests": f"{TEAM_KIT}/run-smoke-tests",
    "check-compiler-errors": f"{TEAM_KIT}/check-compiler-errors",
    "get-pr-comments": f"{TEAM_KIT}/get-pr-comments",
    "fix-merge-conflicts": f"{TEAM_KIT}/fix-merge-conflicts",
    "new-branch-and-pr": f"{TEAM_KIT}/new-branch-and-pr",
    "what-did-i-get-done": f"{TEAM_KIT}/what-did-i-get-done",
    "weekly-review": f"{TEAM_KIT}/weekly-review",
    "deslop": f"{TEAM_KIT}/deslop",
}

# new skill -> list of (upstream skill name, upstream path)
ADAPTED: dict[str, list[tuple[str, str]]] = {
    "understand-codebase": [("how", f"{PSTACK}/how")],
    "recover-design-rationale": [("why", f"{PSTACK}/why")],
    "design-architecture": [("architect", f"{PSTACK}/architect")],
    "compare-designs": [("arena", f"{PSTACK}/arena")],
    "adversarial-review": [("interrogate", f"{PSTACK}/interrogate")],
    "recover-work-context": [("recall", f"{PSTACK}/recall")],
    "work-retrospective": [("reflect", f"{PSTACK}/reflect")],
    "mine-work-patterns": [
        ("automate-me", f"{PSTACK}/automate-me"),
        ("workflow-from-chats", f"{TEAM_KIT}/workflow-from-chats"),
    ],
    "record-evidence": [("show-me-your-work", f"{PSTACK}/show-me-your-work")],
    "create-verification-workflow": [("create-verification-skill", f"{PSTACK}/create-verification-skill")],
    "maintain-verification-workflow": [("maintain-verification-skill", f"{PSTACK}/maintain-verification-skill")],
    "parallelize-work": [("swarm", f"{PSTACK}/swarm")],
    "design-investigation": [("figure-it-out", f"{PSTACK}/figure-it-out")],
    "deliver-software": [("poteto-mode", f"{PSTACK}/poteto-mode")],
    "verify-ui": [("control-ui", f"{TEAM_KIT}/control-ui")],
    "verify-cli": [("control-cli", f"{TEAM_KIT}/control-cli")],
}

ORIGINAL = [
    "preflight-repository",
    "build-execution-contract",
    "certify-pr-head",
    "integrate-pr-stack",
    "trace-artifact-provenance",
    "certify-release",
    "reconcile-project-truth",
    "certify-production-target",
    "certify-database-rollout",
    "certify-mcp-production",
]


def entry(skill: str) -> dict:
    if skill in COPIED:
        return {
            "skill": skill,
            "origin": "cursor/plugins",
            "source_path": COPIED[skill],
            "source_commit": SOURCE_COMMIT,
            "license": LICENSE,
            "mode": "copied",
        }
    if skill in ADAPTED:
        pairs = ADAPTED[skill]
        if len(pairs) == 1:
            source_skill, source_path = pairs[0]
            return {
                "skill": skill,
                "origin": "cursor/plugins",
                "source_skill": source_skill,
                "source_path": source_path,
                "source_commit": SOURCE_COMMIT,
                "license": LICENSE,
                "mode": "adapted",
            }
        return {
            "skill": skill,
            "origin": "cursor/plugins",
            "source_skills": [p[0] for p in pairs],
            "source_paths": [p[1] for p in pairs],
            "source_commit": SOURCE_COMMIT,
            "license": LICENSE,
            "mode": "adapted",
        }
    if skill in ORIGINAL:
        return {"skill": skill, "mode": "original"}
    raise KeyError(skill)


def main() -> int:
    skills = sorted(set(COPIED) | set(ADAPTED) | set(ORIGINAL))
    document = {
        "source_repository": SOURCE_REPOSITORY,
        "source_commit": SOURCE_COMMIT,
        "generated_by": "scripts/build_upstream_sources.py",
        "sources": [entry(skill) for skill in skills],
    }
    OUT.write_text(json.dumps(document, indent=2, sort_keys=False) + "\n")
    counts = {"copied": len(COPIED), "adapted": len(ADAPTED), "original": len(ORIGINAL)}
    print(f"[OK] wrote {OUT.name}: {counts}, total {len(skills)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
