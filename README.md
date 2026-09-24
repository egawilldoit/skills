# Skills

A personal, reusable catalog of Agent Skills for ChatGPT and Codex.

Each skill is a self-contained folder that gives an agent procedural knowledge
for one job: a workflow, the decisions inside it, its hard rules, and the
evidence it must produce. Skills are written once and used across surfaces.

## Purpose

The catalog covers engineering work end to end: understanding a codebase,
designing a change, implementing it, reviewing it, verifying it, landing it,
certifying a release, and reconciling what is actually deployed. It favors
verification over assertion and explicit authority over improvisation.

## OpenAI-compatible structure

The repository is a portable Agent Skills plugin.

```text
skills/
├── README.md
├── plugin.json                 portable plugin manifest
├── LICENSE                     this repository's MIT license
├── THIRD_PARTY_NOTICES.md      upstream attribution
├── upstream-sources.json       machine-readable provenance registry
├── references/
│   └── operating-contract.md   shared vocabulary for owned skills
├── scripts/                    catalog tooling (see below)
├── tests/
│   └── trigger-cases.json      routing test cases for owned skills
└── skills/
    └── <skill-name>/
        ├── SKILL.md            name + description frontmatter, then the workflow
        ├── agents/openai.yaml  UI metadata: display_name, short_description, default_prompt
        ├── references/         optional long-form material
        ├── scripts/            optional deterministic automation
        └── assets/             optional files copied into outputs
```

Every `SKILL.md` uses only `name` and `description` frontmatter. Every skill
ships `agents/openai.yaml` with a human-facing title, a short blurb, and an
example prompt that names the skill as `$skill-name`.

## How skills are organized

Every skill lives directly under `skills/<skill-name>/`. There is no category
nesting yet. A skill is added at the top level and is discoverable by its
description alone.

`SKILL.md` holds the activation contract, workflow, decisions, hard rules, and
output contract. Long material moves into `references/`. Facts that can be
proven deterministically move into `scripts/`. `assets/` is used only for files
copied into outputs. Empty resource folders are not created.

## How upstream skills are handled

Skills derived from [`cursor/plugins`](https://github.com/cursor/plugins) are
pinned to a single source commit and classified by import mode.

```text
UPSTREAM   copied: upstream methodology preserved, packaging normalized
ADAPTED    studied upstream source, reimplemented platform-neutral
ORIGINAL   written for this catalog
```

Copied skills keep their upstream body. The only body edits are packaging
normalization: Cursor-only frontmatter is dropped, and cross-skill references
are remapped to the names used here so no link goes dead. Descriptions and
`agents/openai.yaml` are optimized for routing.

## How adapted skills differ from copied skills

A copied skill is the upstream skill, repackaged. An adapted skill keeps the
problem definition, workflow shape, and decision rules, but is rewritten so it
does not depend on a specific runtime. Adapted skills remove Cursor-only
primitives such as proprietary task APIs, transcript paths, and fixed model
slugs, and describe parallel work in runtime-neutral terms.

## How original skills are added

Original skills come from repeated work in this catalog's domain. They are
written from scratch, are platform-neutral, and use the shared labels in
`references/operating-contract.md`. Each one states its verdicts, hard rules,
and output contract explicitly.

## How source provenance is tracked

`upstream-sources.json` records, for every skill, its mode and, when derived,
its origin repository, source path, source skill, source commit, and license.
The source commit is pinned once for the whole import. `THIRD_PARTY_NOTICES.md`
carries the upstream MIT notices.

## How to validate and update the catalog

```bash
# regenerate agents/openai.yaml from the curated metadata table
python3 scripts/sync_openai_yaml.py

# rebuild upstream-sources.json from the pinned source
python3 scripts/build_upstream_sources.py

# validate structure, metadata, references, leaks, and provenance
python3 scripts/validate_catalog.py

# review description overlap across at-risk clusters
python3 scripts/routing_audit.py

# check owned skills route their trigger cases to the intended skill
python3 scripts/trigger_audit.py

# re-import copied skills from a cursor/plugins checkout
python3 scripts/import_cursor_skills.py --source /path/to/cursor-plugins
```

`validate_catalog.py` is the gate. It fails on invalid frontmatter, name and
directory mismatch, missing or stale `agents/openai.yaml`, broken references,
empty resource folders, placeholders, Cursor-specific coupling, and provenance
gaps.

`tests/trigger-cases.json` holds six representative requests per owned skill:
direct, indirect, incomplete, a nearby request that must not fire, a boundary
case against the closest sibling, and a hard edge case. `trigger_audit.py`
checks the suite structurally and reports where wording drifts toward a
sibling. Real routing is semantic, so the lexical layer is a signal, not a gate.

## Catalog

| Skill | Purpose | Origin | Ownership |
| --- | --- | --- | --- |
| [`blast-radius`](skills/blast-radius/) | Find what a change breaks elsewhere before it ships | `pstack/skills/blast-radius` | UPSTREAM |
| [`check-compiler-errors`](skills/check-compiler-errors/) | Surface and clear compiler and type errors | `cursor-team-kit/skills/check-compiler-errors` | UPSTREAM |
| [`deslop`](skills/deslop/) | Remove dead code and leftover scaffolding | `cursor-team-kit/skills/deslop` | UPSTREAM |
| [`fix-ci`](skills/fix-ci/) | Diagnose and repair a failing CI check | `cursor-team-kit/skills/fix-ci` | UPSTREAM |
| [`fix-merge-conflicts`](skills/fix-merge-conflicts/) | Resolve conflicts while preserving intent | `cursor-team-kit/skills/fix-merge-conflicts` | UPSTREAM |
| [`get-pr-comments`](skills/get-pr-comments/) | Collect and triage review comments on a PR | `cursor-team-kit/skills/get-pr-comments` | UPSTREAM |
| [`loop-on-ci`](skills/loop-on-ci/) | Drive CI to green on the current head | `cursor-team-kit/skills/loop-on-ci` | UPSTREAM |
| [`make-pr-easy-to-review`](skills/make-pr-easy-to-review/) | Improve reviewer ergonomics without behavior change | `cursor-team-kit/skills/make-pr-easy-to-review` | UPSTREAM |
| [`new-branch-and-pr`](skills/new-branch-and-pr/) | Branch, commit, push, and open a clean PR | `cursor-team-kit/skills/new-branch-and-pr` | UPSTREAM |
| [`principle-attack-the-premise`](skills/principle-attack-the-premise/) | Challenge the assumption the task is built on | `pstack/skills/principle-attack-the-premise` | UPSTREAM |
| [`principle-boundary-discipline`](skills/principle-boundary-discipline/) | Validate at system boundaries, trust internal types | `pstack/skills/principle-boundary-discipline` | UPSTREAM |
| [`principle-build-the-lever`](skills/principle-build-the-lever/) | Build the tool that does or proves the work | `pstack/skills/principle-build-the-lever` | UPSTREAM |
| [`principle-encode-lessons-in-structure`](skills/principle-encode-lessons-in-structure/) | Turn a repeated rule into a check, not more text | `pstack/skills/principle-encode-lessons-in-structure` | UPSTREAM |
| [`principle-exhaust-the-design-space`](skills/principle-exhaust-the-design-space/) | Prototype competing options before committing | `pstack/skills/principle-exhaust-the-design-space` | UPSTREAM |
| [`principle-experience-first`](skills/principle-experience-first/) | Choose user delight over implementation convenience | `pstack/skills/principle-experience-first` | UPSTREAM |
| [`principle-fix-root-causes`](skills/principle-fix-root-causes/) | Trace symptoms to the root cause and fix there | `pstack/skills/principle-fix-root-causes` | UPSTREAM |
| [`principle-foundational-thinking`](skills/principle-foundational-thinking/) | Get the core data structures right before logic | `pstack/skills/principle-foundational-thinking` | UPSTREAM |
| [`principle-guard-the-context-window`](skills/principle-guard-the-context-window/) | Route bulk output to subagents, keep summaries | `pstack/skills/principle-guard-the-context-window` | UPSTREAM |
| [`principle-laziness-protocol`](skills/principle-laziness-protocol/) | Prefer deletion and the smallest change that works | `pstack/skills/principle-laziness-protocol` | UPSTREAM |
| [`principle-make-operations-idempotent`](skills/principle-make-operations-idempotent/) | Make retried steps converge to one end state | `pstack/skills/principle-make-operations-idempotent` | UPSTREAM |
| [`principle-migrate-callers-then-delete-legacy-apis`](skills/principle-migrate-callers-then-delete-legacy-apis/) | Move callers and delete the old API in one wave | `pstack/skills/principle-migrate-callers-then-delete-legacy-apis` | UPSTREAM |
| [`principle-minimize-reader-load`](skills/principle-minimize-reader-load/) | Cut layers and hidden state a reader must hold | `pstack/skills/principle-minimize-reader-load` | UPSTREAM |
| [`principle-model-the-domain`](skills/principle-model-the-domain/) | Encode domain rules in types, not conditionals | `pstack/skills/principle-model-the-domain` | UPSTREAM |
| [`principle-outcome-oriented-execution`](skills/principle-outcome-oriented-execution/) | Converge on the target, skip throwaway states | `pstack/skills/principle-outcome-oriented-execution` | UPSTREAM |
| [`principle-prove-it-works`](skills/principle-prove-it-works/) | Verify the real artifact, not a proxy or claim | `pstack/skills/principle-prove-it-works` | UPSTREAM |
| [`principle-redesign-from-first-principles`](skills/principle-redesign-from-first-principles/) | Integrate new needs as if known from day one | `pstack/skills/principle-redesign-from-first-principles` | UPSTREAM |
| [`principle-separate-before-serializing-shared-state`](skills/principle-separate-before-serializing-shared-state/) | Remove shared writes before adding locking | `pstack/skills/principle-separate-before-serializing-shared-state` | UPSTREAM |
| [`principle-sequence-verifiable-units`](skills/principle-sequence-verifiable-units/) | Break work into units that each end verifiable | `pstack/skills/principle-sequence-verifiable-units` | UPSTREAM |
| [`principle-subtract-before-you-add`](skills/principle-subtract-before-you-add/) | Remove dead weight before building on the base | `pstack/skills/principle-subtract-before-you-add` | UPSTREAM |
| [`principle-test-behavior-not-implementation`](skills/principle-test-behavior-not-implementation/) | Assert observable behavior, not internal structure | `pstack/skills/principle-test-behavior-not-implementation` | UPSTREAM |
| [`principle-type-system-discipline`](skills/principle-type-system-discipline/) | Make illegal states unrepresentable in the types | `pstack/skills/principle-type-system-discipline` | UPSTREAM |
| [`review-and-ship`](skills/review-and-ship/) | Finish one ordinary branch or PR cleanly | `cursor-team-kit/skills/review-and-ship` | UPSTREAM |
| [`run-smoke-tests`](skills/run-smoke-tests/) | Run the project's existing smoke suite | `cursor-team-kit/skills/run-smoke-tests` | UPSTREAM |
| [`tdd`](skills/tdd/) | Drive changes from a failing test to a proven fix | `pstack/skills/tdd` | UPSTREAM |
| [`technical-writing`](skills/technical-writing/) | Write and review docs, RFCs, and PR descriptions | `pstack/skills/technical-writing` | UPSTREAM |
| [`typescript-best-practices`](skills/typescript-best-practices/) | Apply TypeScript typing and design conventions | `pstack/skills/typescript-best-practices` | UPSTREAM |
| [`unslop`](skills/unslop/) | Cut AI tells and filler from any writing | `pstack/skills/unslop` | UPSTREAM |
| [`verify-this`](skills/verify-this/) | Prove one falsifiable claim with fresh evidence | `cursor-team-kit/skills/verify-this` | UPSTREAM |
| [`weekly-review`](skills/weekly-review/) | Summarize a week of authored work | `cursor-team-kit/skills/weekly-review` | UPSTREAM |
| [`what-did-i-get-done`](skills/what-did-i-get-done/) | Summarize the commits you authored recently | `cursor-team-kit/skills/what-did-i-get-done` | UPSTREAM |
| [`adversarial-review`](skills/adversarial-review/) | Independently challenge a change's correctness | `interrogate` | ADAPTED |
| [`compare-designs`](skills/compare-designs/) | Generate and compare candidate designs before committing | `arena` | ADAPTED |
| [`create-verification-workflow`](skills/create-verification-workflow/) | Build a project-local harness that drives the app | `create-verification-skill` | ADAPTED |
| [`deliver-software`](skills/deliver-software/) | Route non-trivial engineering work to the right skill | `poteto-mode` | ADAPTED |
| [`design-architecture`](skills/design-architecture/) | Produce an implementable architecture contract | `architect` | ADAPTED |
| [`design-investigation`](skills/design-investigation/) | Plan an investigation when no narrower workflow fits | `figure-it-out` | ADAPTED |
| [`maintain-verification-workflow`](skills/maintain-verification-workflow/) | Audit a verification workflow against the current app | `maintain-verification-skill` | ADAPTED |
| [`mine-work-patterns`](skills/mine-work-patterns/) | Find recurring work worth encoding as a skill | `automate-me + workflow-from-chats` | ADAPTED |
| [`parallelize-work`](skills/parallelize-work/) | Fan out work that can be split without conflict | `swarm` | ADAPTED |
| [`record-evidence`](skills/record-evidence/) | Keep an auditable decision and evidence ledger | `show-me-your-work` | ADAPTED |
| [`recover-design-rationale`](skills/recover-design-rationale/) | Recover why code is shaped this way, with sources | `why` | ADAPTED |
| [`recover-work-context`](skills/recover-work-context/) | Reconstruct the current state of ongoing work | `recall` | ADAPTED |
| [`understand-codebase`](skills/understand-codebase/) | Build a mental model of how a subsystem works | `how` | ADAPTED |
| [`verify-cli`](skills/verify-cli/) | Verify CLI or TUI behavior with real execution | `control-cli` | ADAPTED |
| [`verify-ui`](skills/verify-ui/) | Verify real browser or UI behavior with evidence | `control-ui` | ADAPTED |
| [`work-retrospective`](skills/work-retrospective/) | Turn a finished session into durable lessons | `reflect` | ADAPTED |
| [`build-execution-contract`](skills/build-execution-contract/) | Turn a requirement into a bounded agent contract | `-` | ORIGINAL |
| [`certify-database-rollout`](skills/certify-database-rollout/) | Certify a migration across its real lifecycle | `-` | ORIGINAL |
| [`certify-mcp-production`](skills/certify-mcp-production/) | Certify a production MCP server end to end | `-` | ORIGINAL |
| [`certify-pr-head`](skills/certify-pr-head/) | Prove PR evidence matches the exact current head | `-` | ORIGINAL |
| [`certify-production-target`](skills/certify-production-target/) | Confirm the exact target before production mutation | `-` | ORIGINAL |
| [`certify-release`](skills/certify-release/) | Certify code, runtime, and product gates for a release | `-` | ORIGINAL |
| [`integrate-pr-stack`](skills/integrate-pr-stack/) | Land stacked PRs one at a time without drift | `-` | ORIGINAL |
| [`preflight-repository`](skills/preflight-repository/) | Establish exact repo reality before serious work | `-` | ORIGINAL |
| [`reconcile-project-truth`](skills/reconcile-project-truth/) | Resolve contradictions across project sources | `-` | ORIGINAL |
| [`trace-artifact-provenance`](skills/trace-artifact-provenance/) | Trace source to artifact to release lineage | `-` | ORIGINAL |

Catalog counts: 40 copied, 16 adapted, 10 original, 66 total.
