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

## Agent Plugins structure

This repository is a portable [Agent Plugins](https://agent-plugins.org/)
package. `plugin.json` is the portable manifest, conforming to the Agent
Plugins 1.0.0 schema.

```text
skills/
├── README.md
├── plugin.json                        portable Agent Plugins manifest (1.0.0)
├── LICENSE                            this repository's MIT license
├── THIRD_PARTY_NOTICES.md             upstream attribution
├── upstream-sources.json              machine-readable provenance registry
├── references/
│   ├── operating-contract.md          shared vocabulary for owned skills
│   ├── agent-plugin-schema-1.0.0.json vendored canonical schema (offline validation)
│   └── agent-plugin-schema-1.0.0.sha256 pinned digest of the vendored schema
├── scripts/                           catalog tooling (see below)
├── requirements-ci.txt                exact-pinned CI dependency lock
├── tests/
│   ├── trigger-cases.json             routing test cases for owned skills
│   └── test_*.py                      behavior tests for the deterministic helpers
├── .github/
│   └── workflows/
│       └── catalog-validation.yml     first-party CI
└── skills/
    └── <skill-name>/
        ├── SKILL.md                   name + description frontmatter, then the workflow
        ├── agents/openai.yaml         OpenAI UI metadata for the skill
        ├── references/                optional long-form material
        ├── scripts/                   optional deterministic automation
        └── assets/                    optional files copied into outputs
```

Key packaging facts:

- `plugin.json` is the portable Agent Plugins manifest. It declares `$schema`,
  identity, and publisher metadata, and nothing else at the root.
- Portable packages auto-discover skills from the root `skills/` directory, so
  the manifest does **not** declare a `skills` field.
- OpenAI-specific install-surface metadata (presentation) lives under
  `extensions.com.openai.interface`, not at the manifest root.
- There is no MCP server, so there is no `mcp.json`.

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
does not depend on a specific runtime.

Adapted skills remove Cursor-only primitives such as proprietary task APIs,
transcript paths, and fixed model slugs. The GitHub workflows are also
capability-neutral: they prefer a native or connected GitHub capability, fall
back to the authenticated GitHub CLI when it is available, and report the
capability as unavailable rather than claiming an operation that did not
happen. They resolve the actual base branch instead of assuming `main`.

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
# validate the portable manifest against the Agent Plugins 1.0.0 schema
python3 scripts/validate_plugin_manifest.py

# validate catalog structure, metadata, references, leaks, and provenance
python3 scripts/validate_catalog.py

# check agents/openai.yaml is current
python3 scripts/sync_openai_yaml.py --check

# check every skill-local operating-contract copy matches the canonical file
python3 scripts/sync_operating_contract.py --check

# review description overlap across at-risk clusters
python3 scripts/routing_audit.py

# check owned skills route their trigger cases to the intended skill
python3 scripts/trigger_audit.py

# run the deterministic helper test suite
python3 -m unittest discover -s tests -p 'test_*.py'

# regenerate agents/openai.yaml from the curated metadata table
python3 scripts/sync_openai_yaml.py

# rebuild upstream-sources.json from the pinned source
python3 scripts/build_upstream_sources.py

# re-import copied skills from a pinned cursor/plugins checkout
python3 scripts/import_cursor_skills.py --source /path/to/cursor-plugins
```

Validation has these layers:

- `validate_plugin_manifest.py` validates `plugin.json` against the official
  Agent Plugins 1.0.0 JSON Schema. The repository vendors the 1.0.0 schema at
  `references/agent-plugin-schema-1.0.0.json` and pins its expected SHA-256
  digest at `references/agent-plugin-schema-1.0.0.sha256`; offline validation
  refuses a schema whose digest differs from the committed pin (this is local
  integrity, not a live comparison against the canonical URL).
- `validate_catalog.py` is the repository catalog gate. It calls the manifest
  validator, then checks skill structure, frontmatter, `agents/openai.yaml`,
  reference integrity, empty resource folders, placeholders, Cursor-specific
  coupling, provenance coverage, and the combined `plugin:skill` identity
  length (every combined identity must stay at or under 64 characters).
- The legacy OpenAI `openai/skills` `skill-creator` `quick_validate.py` is an
  optional historical cross-check of skill anatomy. It is not the current
  plugin-packaging validator and is not part of CI.

The plugin package identifier is `ega-skills` (short enough that every
combined `ega-skills:<skill>` identity fits the 64-character submission
constraint); the human-facing display name stays "egawilldoit skills".

`tests/trigger-cases.json` holds six representative requests per owned skill:
direct, indirect, incomplete, a nearby request that must not fire, a boundary
case against the closest sibling, and a hard edge case. `trigger_audit.py`
checks the suite structurally and reports where wording drifts toward a
sibling. Real routing is semantic, so the lexical layer is a signal, not a gate.
`routing_audit.py` and `trigger_audit.py` are routing metadata lint and
trigger wording regression checks; they are static signals, not proof that a
model will semantically route every skill correctly.

`tests/` also contains behavior tests for the deterministic proof helpers
(`preflight.py`, `certify_pr_head.py`, `provenance_manifest.py`,
`discover_stack.py`, the catalog and manifest validators, the Cursor source-pin
import guard, the operating-contract sync, `assert_checkout_sha.py`, and
`record-evidence/scripts/log.sh`). They use standard-library `unittest` and
temporary git repositories; no unit test depends on live GitHub.

## Source pin enforcement

The catalog pins a single Cursor source commit
(`12d587dfb20741cafc376c42c696c5f6e2a64487`). `import_cursor_skills.py` refuses
to import from a checkout whose HEAD does not equal that pin, or whose origin
is not `cursor/plugins`; a mismatch hard-fails. Updating the pin is a
deliberate operation: change the pin, regenerate `upstream-sources.json`, and
re-import together.

## Shared operating contract

`references/operating-contract.md` is the canonical copy. Skill-local copies
exist so skills stay self-contained when packaged independently;
`scripts/sync_operating_contract.py --check` fails on any drift between the
canonical file and any skill-local copy, and CI enforces it.

## CI

`.github/workflows/catalog-validation.yml` produces two distinct validation
guarantees for pull requests:

```text
validate-head    checks out the exact PR head (github.event.pull_request.head.sha),
                 proves the executed SHA equals the PR head, and runs the full
                 gate suite plus the deterministic helper tests
validate-merge   validates the normal GitHub synthetic PR merge result and
                 proves the executed SHA differs from the PR head, showing the
                 proposed code also validates when combined with the current base
validate-main    for pushes to main, validates the exact pushed SHA
```

Both PR jobs run the full suite:

```text
scripts/validate_plugin_manifest.py
scripts/validate_catalog.py
scripts/sync_openai_yaml.py --check
scripts/sync_operating_contract.py --check
scripts/routing_audit.py
scripts/trigger_audit.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
```

Exact-head validation and merge-result validation are separate evidence
classes and are never conflated: a green `validate-merge` does not certify the
PR head itself; only `validate-head` does. Actions are pinned to immutable
full commit SHAs (`actions/checkout@11d5960a326750d5838078e36cf38b85af677262`,
`actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065`), and
validation dependencies are exact-pinned in `requirements-ci.txt`.

## Catalog

| Skill | Purpose | Origin | Ownership |
| --- | --- | --- | --- |
| [`blast-radius`](skills/blast-radius/) | Find what a change breaks elsewhere before it ships | `pstack/skills/blast-radius` | UPSTREAM |
| [`check-compiler-errors`](skills/check-compiler-errors/) | Surface and clear compiler and type errors | `cursor-team-kit/skills/check-compiler-errors` | UPSTREAM |
| [`fix-merge-conflicts`](skills/fix-merge-conflicts/) | Resolve conflicts while preserving intent | `cursor-team-kit/skills/fix-merge-conflicts` | UPSTREAM |
| [`get-pr-comments`](skills/get-pr-comments/) | Collect and triage review comments on a PR | `cursor-team-kit/skills/get-pr-comments` | UPSTREAM |
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
| [`deslop`](skills/deslop/) | Remove dead code and leftover scaffolding | `deslop` | ADAPTED |
| [`fix-ci`](skills/fix-ci/) | Diagnose and repair a failing CI check | `fix-ci` | ADAPTED |
| [`loop-on-ci`](skills/loop-on-ci/) | Drive CI to green on the current head | `loop-on-ci` | ADAPTED |
| [`maintain-verification-workflow`](skills/maintain-verification-workflow/) | Audit a verification workflow against the current app | `maintain-verification-skill` | ADAPTED |
| [`make-pr-easy-to-review`](skills/make-pr-easy-to-review/) | Improve reviewer ergonomics without behavior change | `make-pr-easy-to-review` | ADAPTED |
| [`mine-work-patterns`](skills/mine-work-patterns/) | Find recurring work worth encoding as a skill | `automate-me + workflow-from-chats` | ADAPTED |
| [`new-branch-and-pr`](skills/new-branch-and-pr/) | Branch, commit, push, and open a clean PR | `new-branch-and-pr` | ADAPTED |
| [`parallelize-work`](skills/parallelize-work/) | Fan out work that can be split without conflict | `swarm` | ADAPTED |
| [`record-evidence`](skills/record-evidence/) | Keep an auditable decision and evidence ledger | `show-me-your-work` | ADAPTED |
| [`recover-design-rationale`](skills/recover-design-rationale/) | Recover why code is shaped this way, with sources | `why` | ADAPTED |
| [`recover-work-context`](skills/recover-work-context/) | Reconstruct the current state of ongoing work | `recall` | ADAPTED |
| [`review-and-ship`](skills/review-and-ship/) | Finish one ordinary branch or PR cleanly | `review-and-ship` | ADAPTED |
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

Catalog counts: 34 copied, 22 adapted, 10 original, 66 total.
