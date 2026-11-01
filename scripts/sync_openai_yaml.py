#!/usr/bin/env python3
"""Generate and check agents/openai.yaml for every skill.

The interface metadata is curated per skill: display_name, short_description,
and default_prompt are written by hand, not derived mechanically, because they
decide how the skill is presented and invoked.

Rules enforced (from the OpenAI skill-creator openai.yaml reference):
  * keys unquoted, all string values double quoted
  * short_description is 25-64 characters
  * default_prompt names the skill as $skill-name

Usage:
    python3 scripts/sync_openai_yaml.py            # write files
    python3 scripts/sync_openai_yaml.py --check     # verify files are current
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"

# name -> (display_name, short_description, default_prompt)
METADATA: dict[str, tuple[str, str, str]] = {
    # --- copied: pstack ---
    "blast-radius": (
        "Blast Radius",
        "Find what a change breaks elsewhere before it ships",
        "Use $blast-radius to find what this change could break elsewhere before it ships.",
    ),
    "tdd": (
        "Test-Driven Development",
        "Drive changes from a failing test to a proven fix",
        "Use $tdd to build this change from a failing test.",
    ),
    "technical-writing": (
        "Technical Writing",
        "Write and review docs, RFCs, and PR descriptions",
        "Use $technical-writing to tighten this RFC and its structure.",
    ),
    "typescript-best-practices": (
        "TypeScript Best Practices",
        "Apply TypeScript typing and design conventions",
        "Use $typescript-best-practices when editing these .ts files.",
    ),
    "unslop": (
        "Unslop",
        "Cut AI tells and filler from any writing",
        "Use $unslop to strip the AI tells from this text.",
    ),
    "principle-attack-the-premise": (
        "Attack the Premise",
        "Challenge the assumption the task is built on",
        "Use $principle-attack-the-premise before building on this assumption.",
    ),
    "principle-boundary-discipline": (
        "Boundary Discipline",
        "Validate at system boundaries, trust internal types",
        "Use $principle-boundary-discipline when wiring this validation.",
    ),
    "principle-build-the-lever": (
        "Build the Lever",
        "Build the tool that does or proves the work",
        "Use $principle-build-the-lever to script this migration instead of editing by hand.",
    ),
    "principle-encode-lessons-in-structure": (
        "Encode Lessons in Structure",
        "Turn a repeated rule into a check, not more text",
        "Use $principle-encode-lessons-in-structure to encode this rule as a lint.",
    ),
    "principle-exhaust-the-design-space": (
        "Exhaust the Design Space",
        "Prototype competing options before committing",
        "Use $principle-exhaust-the-design-space to prototype two or three options first.",
    ),
    "principle-experience-first": (
        "Experience First",
        "Choose user delight over implementation convenience",
        "Use $principle-experience-first to weigh this UX tradeoff.",
    ),
    "principle-fix-root-causes": (
        "Fix Root Causes",
        "Trace symptoms to the root cause and fix there",
        "Use $principle-fix-root-causes to find why this keeps failing.",
    ),
    "principle-foundational-thinking": (
        "Foundational Thinking",
        "Get the core data structures right before logic",
        "Use $principle-foundational-thinking before designing these types.",
    ),
    "principle-guard-the-context-window": (
        "Guard the Context Window",
        "Route bulk output to subagents, keep summaries",
        "Use $principle-guard-the-context-window before reading these large files.",
    ),
    "principle-laziness-protocol": (
        "Laziness Protocol",
        "Prefer deletion and the smallest change that works",
        "Use $principle-laziness-protocol to shrink this refactor.",
    ),
    "principle-make-operations-idempotent": (
        "Make Operations Idempotent",
        "Make retried steps converge to one end state",
        "Use $principle-make-operations-idempotent when designing this retry loop.",
    ),
    "principle-migrate-callers-then-delete-legacy-apis": (
        "Migrate Callers, Delete Legacy",
        "Move callers and delete the old API in one wave",
        "Use $principle-migrate-callers-then-delete-legacy-apis to remove this old API.",
    ),
    "principle-minimize-reader-load": (
        "Minimize Reader Load",
        "Cut layers and hidden state a reader must hold",
        "Use $principle-minimize-reader-load to simplify this call path.",
    ),
    "principle-model-the-domain": (
        "Model the Domain",
        "Encode domain rules in types, not conditionals",
        "Use $principle-model-the-domain to replace these scattered branches.",
    ),
    "principle-outcome-oriented-execution": (
        "Outcome-Oriented Execution",
        "Converge on the target, skip throwaway states",
        "Use $principle-outcome-oriented-execution to plan this migration.",
    ),
    "principle-prove-it-works": (
        "Prove It Works",
        "Verify the real artifact, not a proxy or claim",
        "Use $principle-prove-it-works before declaring this done.",
    ),
    "principle-redesign-from-first-principles": (
        "Redesign From First Principles",
        "Integrate new needs as if known from day one",
        "Use $principle-redesign-from-first-principles to fold in this new requirement.",
    ),
    "principle-separate-before-serializing-shared-state": (
        "Separate Before Serializing",
        "Remove shared writes before adding locking",
        "Use $principle-separate-before-serializing-shared-state when two writers share this file.",
    ),
    "principle-sequence-verifiable-units": (
        "Sequence Verifiable Units",
        "Break work into units that each end verifiable",
        "Use $principle-sequence-verifiable-units to split this sweep.",
    ),
    "principle-subtract-before-you-add": (
        "Subtract Before You Add",
        "Remove dead weight before building on the base",
        "Use $principle-subtract-before-you-add before adding this feature.",
    ),
    "principle-test-behavior-not-implementation": (
        "Test Behavior, Not Implementation",
        "Assert observable behavior, not internal structure",
        "Use $principle-test-behavior-not-implementation to rewrite these tests.",
    ),
    "principle-type-system-discipline": (
        "Type System Discipline",
        "Make illegal states unrepresentable in the types",
        "Use $principle-type-system-discipline when shaping this API.",
    ),
    # --- copied: cursor-team-kit ---
    "verify-this": (
        "Verify This",
        "Prove one falsifiable claim with fresh evidence",
        "Use $verify-this to prove this performance claim.",
    ),
    "review-and-ship": (
        "Review and Ship",
        "Finish one ordinary branch or PR cleanly",
        "Use $review-and-ship to take this branch to a merge-ready PR.",
    ),
    "make-pr-easy-to-review": (
        "Make PR Easy to Review",
        "Improve reviewer ergonomics without behavior change",
        "Use $make-pr-easy-to-review to split this diff for reviewers.",
    ),
    "loop-on-ci": (
        "Loop on CI",
        "Drive CI to green on the current head",
        "Use $loop-on-ci to get this PR's checks passing.",
    ),
    "fix-ci": (
        "Fix CI",
        "Diagnose and repair a failing CI check",
        "Use $fix-ci to repair the failing build job.",
    ),
    "run-smoke-tests": (
        "Run Smoke Tests",
        "Run smoke tests and report real failures",
        "Use $run-smoke-tests to run the existing smoke suite and report any failures.",
    ),
    "check-compiler-errors": (
        "Check Compiler Errors",
        "Inspect compiler and type-check failures",
        "Use $check-compiler-errors to inspect compiler and type-check failures on this branch.",
    ),
    "get-pr-comments": (
        "Get PR Comments",
        "Collect and triage review comments on a PR",
        "Use $get-pr-comments to gather what reviewers asked for.",
    ),
    "fix-merge-conflicts": (
        "Fix Merge Conflicts",
        "Resolve conflicts while preserving intent",
        "Use $fix-merge-conflicts on this rebase conflict.",
    ),
    "new-branch-and-pr": (
        "New Branch and PR",
        "Branch, commit, push, and open a clean PR",
        "Use $new-branch-and-pr to ship this fix.",
    ),
    "what-did-i-get-done": (
        "What Did I Get Done",
        "Summarize the commits you authored recently",
        "Use $what-did-i-get-done to summarize my last few commits.",
    ),
    "weekly-review": (
        "Weekly Review",
        "Summarize a week of authored work",
        "Use $weekly-review to summarize this week's work.",
    ),
    "deslop": (
        "Deslop",
        "Remove dead code and leftover scaffolding",
        "Use $deslop to clean up this branch before review.",
    ),
    # --- adapted ---
    "understand-codebase": (
        "Understand Codebase",
        "Build a mental model of how a subsystem works",
        "Use $understand-codebase to explain how the billing subsystem works.",
    ),
    "recover-design-rationale": (
        "Design Rationale Recovery",
        "Recover why code is shaped this way, with sources",
        "Use $recover-design-rationale to find why this retry limit exists.",
    ),
    "design-architecture": (
        "Design Architecture",
        "Produce an implementable architecture contract",
        "Use $design-architecture before building this subsystem.",
    ),
    "compare-designs": (
        "Compare Designs",
        "Generate and compare candidate designs before committing",
        "Use $compare-designs to weigh these two approaches.",
    ),
    "adversarial-review": (
        "Adversarial Review",
        "Independently challenge a change's correctness",
        "Use $adversarial-review to stress-test this diff.",
    ),
    "recover-work-context": (
        "Recover Work Context",
        "Reconstruct the current state of ongoing work",
        "Use $recover-work-context to catch me up on this project.",
    ),
    "work-retrospective": (
        "Work Retrospective",
        "Turn a finished session into durable lessons",
        "Use $work-retrospective on today's session.",
    ),
    "mine-work-patterns": (
        "Mine Work Patterns",
        "Find recurring work worth encoding as a skill",
        "Use $mine-work-patterns over the last month of work.",
    ),
    "record-evidence": (
        "Record Evidence",
        "Keep an auditable decision and evidence ledger",
        "Use $record-evidence for this long autonomous run.",
    ),
    "create-verification-workflow": (
        "Create Verification Workflow",
        "Build a project-local harness that drives the app",
        "Use $create-verification-workflow to set up end-to-end checks for this app.",
    ),
    "maintain-verification-workflow": (
        "Maintain Verification Workflow",
        "Audit a verification workflow against the current app",
        "Use $maintain-verification-workflow to check our verification skill is still accurate.",
    ),
    "parallelize-work": (
        "Parallelize Work",
        "Fan out work that can be split without conflict",
        "Use $parallelize-work to cover these modules in parallel.",
    ),
    "design-investigation": (
        "Design Investigation",
        "Plan an investigation when no narrower workflow fits",
        "Use $design-investigation to plan this large migration.",
    ),
    "deliver-software": (
        "Deliver Software",
        "Route non-trivial engineering work to the right skill",
        "Use $deliver-software to route this task.",
    ),
    "verify-ui": (
        "Verify UI",
        "Verify real browser or UI behavior with evidence",
        "Use $verify-ui to check this checkout flow in a browser.",
    ),
    "verify-cli": (
        "Verify CLI",
        "Verify CLI or TUI behavior with real execution",
        "Use $verify-cli to prove this command works.",
    ),
    # --- original ---
    "preflight-repository": (
        "Repository Preflight",
        "Establish exact repo reality before serious work",
        "Use $preflight-repository before I start on this checkout.",
    ),
    "build-execution-contract": (
        "Build Execution Contract",
        "Turn a requirement into a bounded agent contract",
        "Use $build-execution-contract to brief a delegate agent.",
    ),
    "certify-pr-head": (
        "PR Head Certification",
        "Prove PR evidence matches the exact current head",
        "Use $certify-pr-head before calling this PR merge-ready.",
    ),
    "integrate-pr-stack": (
        "Integrate PR Stack",
        "Land stacked PRs one at a time without drift",
        "Use $integrate-pr-stack to land this stack.",
    ),
    "trace-artifact-provenance": (
        "Artifact Provenance",
        "Trace source to artifact to release lineage",
        "Use $trace-artifact-provenance to pin this build to its source.",
    ),
    "certify-release": (
        "Release Certification",
        "Certify code, runtime, and product gates for a release",
        "Use $certify-release before calling this production-ready.",
    ),
    "reconcile-project-truth": (
        "Reconcile Project Truth",
        "Resolve contradictions across project sources",
        "Use $reconcile-project-truth to settle what is actually deployed.",
    ),
    "certify-production-target": (
        "Production Target Certification",
        "Confirm the exact target before production mutation",
        "Use $certify-production-target before this production change.",
    ),
    "certify-database-rollout": (
        "Database Rollout Certification",
        "Certify a migration across its real lifecycle",
        "Use $certify-database-rollout before applying this migration.",
    ),
    "certify-mcp-production": (
        "MCP Production Certification",
        "Certify a production MCP server end to end",
        "Use $certify-mcp-production before publishing this MCP server.",
    ),
}

MIN_SHORT = 25
MAX_SHORT = 64


def render(name: str, display_name: str, short: str, prompt: str) -> str:
    return (
        "interface:\n"
        f'  display_name: "{display_name}"\n'
        f'  short_description: "{short}"\n'
        f'  default_prompt: "{prompt}"\n'
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    skill_names = sorted(p.name for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file())
    problems: list[str] = []

    missing = sorted(set(skill_names) - set(METADATA))
    extra = sorted(set(METADATA) - set(skill_names))
    for name in missing:
        problems.append(f"{name}: no curated interface metadata")
    for name in extra:
        problems.append(f"{name}: metadata exists but no skill directory")

    stale: list[str] = []
    for name in skill_names:
        if name not in METADATA:
            continue
        display_name, short, prompt = METADATA[name]
        if not (MIN_SHORT <= len(short) <= MAX_SHORT):
            problems.append(f"{name}: short_description length {len(short)} outside {MIN_SHORT}-{MAX_SHORT}")
        if f"${name}" not in prompt:
            problems.append(f"{name}: default_prompt does not mention ${name}")

        target = SKILLS_DIR / name / "agents" / "openai.yaml"
        content = render(name, display_name, short, prompt)
        if args.check:
            if not target.is_file() or target.read_text() != content:
                stale.append(name)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)

    for problem in problems:
        print(f"[ERROR] {problem}")
    if args.check:
        for name in stale:
            print(f"[ERROR] {name}: agents/openai.yaml is missing or out of date")
        if problems or stale:
            return 1
        print(f"[OK] {len(skill_names)} skills have current agents/openai.yaml")
        return 0
    if problems:
        return 1
    print(f"[OK] wrote agents/openai.yaml for {len(skill_names)} skills")
    return 0


if __name__ == "__main__":
    sys.exit(main())
