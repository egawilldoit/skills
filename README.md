# Skills

Source catalog for portable Agent Skills published as the `ega-skills` plugin.

The active catalog is **empty**: zero skills under `skills/`. This repository is
the clean source starting point. Skills are added here, validated here, and then
packaged or consumed by the platform; removing the active skills did not delete
history, licensing, or attribution.

## Purpose

The catalog is structured to hold self-contained skills for engineering work:
understanding a codebase, designing a change, implementing it, reviewing it,
verifying it, landing it, certifying a release, and reconciling what is actually
deployed. It favors verification over assertion and explicit authority over
improvisation. No skill is currently active.

## Agent Plugins structure

This repository is a portable [Agent Plugins](https://agent-plugins.org/)
package. `plugin.json` is the portable manifest, conforming to the Agent
Plugins 1.0.0 schema.

```text
skills/
├── README.md                          this file
├── plugin.json                        portable Agent Plugins manifest (1.0.0)
├── LICENSE                            this repository's MIT license
├── THIRD_PARTY_NOTICES.md             upstream attribution (retained)
├── upstream-sources.json              provenance registry (sources: [])
├── references/
│   ├── operating-contract.md          shared vocabulary for future skills
│   ├── agent-plugin-schema-1.0.0.json vendored canonical schema (offline validation)
│   └── agent-plugin-schema-1.0.0.sha256 pinned digest of the vendored schema
├── scripts/                           catalog tooling (see below)
├── requirements-ci.txt                exact-pinned CI dependency lock
├── tests/
│   ├── trigger-cases.json             routing test cases ([] for an empty catalog)
│   └── test_*.py                      behavior tests for the deterministic helpers
├── .github/
│   └── workflows/
│       └── catalog-validation.yml     first-party CI
└── skills/
    └── .gitkeep                       keeps the auto-discovery directory tracked
```

Key packaging facts:

- `plugin.json` is the portable Agent Plugins manifest. It declares `$schema`,
  identity, and publisher metadata, and nothing else at the root.
- Portable packages auto-discover skills from the root `skills/` directory, so
  the manifest does **not** declare a `skills` field. An empty `skills/`
  directory is a valid discovery result.
- OpenAI-specific install-surface metadata (presentation) lives under
  `extensions.com.openai.interface`, not at the manifest root. Its default
  prompts describe catalog operations rather than removed skills.
- There is no MCP server, so there is no `mcp.json`.

When a skill is added it lives directly under `skills/<skill-name>/` with
`SKILL.md` (only `name` and `description` frontmatter), `ega.yaml`, and
`agents/openai.yaml`, plus optional `references/`, `scripts/`, and `assets/`.
There is no category nesting. `agents/openai.yaml` carries a human-facing
title, a short blurb, and an example prompt naming the skill as `$skill-name`.

## Upstream provenance and attribution

Skills derived from [`cursor/plugins`](https://github.com/cursor/plugins) are
pinned to a single source commit and classified by import mode:

```text
UPSTREAM   copied: upstream methodology preserved, packaging normalized
ADAPTED    studied upstream source, reimplemented platform-neutral
ORIGINAL   written for this catalog
```

`upstream-sources.json` is the machine-readable provenance registry. It keeps
the pinned `source_repository` and `source_commit`, and its `sources` array is
empty because there are no active skills. `THIRD_PARTY_NOTICES.md` retains the
upstream MIT license notices and the historical copied/adapted attribution;
those notices are kept even while no upstream skill is active. Earlier
per-skill provenance records, skill contents, and generated metadata remain
recoverable from Git history.

`scripts/build_upstream_sources.py` regenerates `upstream-sources.json` from
its mode tables. Those tables are empty for the empty catalog and are populated
only when adding a sourced skill. `scripts/import_cursor_skills.py` uses the
same single pinned source commit (`12d587dfb20741cafc376c42c696c5f6e2a64487`)
and refuses to import from a checkout at any other commit or origin. Updating
the pin is a deliberate operation: change the pin, regenerate
`upstream-sources.json`, and re-import together.

## EGA routing metadata

Every skill added to the catalog carries a local `ega.yaml` routing-metadata
companion file (`schema_version: 1`). These files are local package/routing
metadata authored for this catalog; they do not change any skill's provenance
classification, and they do not claim authorship of copied upstream
methodology. The EGA runtime and its V1 schema remain canonical;
`scripts/validate_ega_metadata.py` is a source-side compatibility guard that
checks the repository's `ega.yaml` files against the EGA routing-metadata
contract so a metadata regression is caught in CI before the catalog reaches
the EGA importer.

## Shared operating contract

`references/operating-contract.md` is the canonical source of shared vocabulary.
A skill that relies on those terms copies it into its own `references/` folder
so it stays self-contained when packaged independently;
`scripts/sync_operating_contract.py --check` fails on any drift between the
canonical file and any skill-local copy, and CI enforces it. With no skills,
there are no copies and the check passes.

## Add, edit, or remove a skill

Zero skills is a valid state. Every gate below still runs; malformed metadata,
missing provenance coverage, and stale generated files still fail.

**Add a skill**

1. Create `skills/<skill-name>/` (kebab-case, matching
   `^[a-z0-9]+(-[a-z0-9]+)*$`). Add `SKILL.md` with only `name` and
   `description` frontmatter, plus `ega.yaml` with routing triggers.
2. Add the curated interface entry to `METADATA` in
   `scripts/sync_openai_yaml.py`, then run that script to generate
   `agents/openai.yaml`. Never hand-edit the generated file.
3. If the skill is sourced or adapted, add its entry to
   `scripts/build_upstream_sources.py` and, for copied skills,
   `scripts/import_cursor_skills.py`. Regenerate `upstream-sources.json`.
4. Add a case to `tests/trigger-cases.json` with all eight routing fields. Add
   the skill to any relevant cluster in `scripts/routing_audit.py`.
5. Add the row to the Catalog table below, then run the full gate sequence.

**Edit a skill**

1. Change `SKILL.md`, `ega.yaml`, or its resources. Keep the description,
   triggers, and trigger-case wording aligned so routing does not drift.
2. If the interface presentation changed, edit the curated entry in
   `scripts/sync_openai_yaml.py` and regenerate `agents/openai.yaml`.
3. If provenance changed, update the generator tables and regenerate
   `upstream-sources.json`. Run the full gate sequence.

**Remove a skill**

1. `git rm -r skills/<skill-name>/`. Historical content stays in Git history.
2. Remove its entries from `METADATA` in `scripts/sync_openai_yaml.py`, the mode
   tables in `scripts/build_upstream_sources.py`, the import tables in
   `scripts/import_cursor_skills.py`, any cluster in `scripts/routing_audit.py`,
   `tests/trigger-cases.json`, and the Catalog table below.
3. Regenerate `upstream-sources.json` and `agents/openai.yaml`, then run the
   full gate sequence. Keep `THIRD_PARTY_NOTICES.md` and attribution intact.

Do not weaken a validator to make a failing skill pass, and do not add dummy
skills to make a gate green.

## Validate the catalog

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

# check every skill routes its trigger cases to the intended skill
python3 scripts/trigger_audit.py

# validate EGA routing metadata (ega.yaml) against the V1 compatibility guard
python3 scripts/validate_ega_metadata.py

# run the deterministic helper test suite
python3 -m unittest discover -s tests -p 'test_*.py' -v

# final whitespace check
git diff --check
```

Regeneration and import commands (used when adding or removing a skill):

```bash
python3 scripts/sync_openai_yaml.py
python3 scripts/build_upstream_sources.py
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
  length (every combined identity must stay at or under 64 characters). With
  zero skills, provenance must also be empty; a stale source entry fails.
- `sync_openai_yaml.py --check` fails when a catalog skill has no curated
  interface metadata or when a generated file is missing or stale.
- `validate_ega_metadata.py` checks each skill's `ega.yaml` against the V1
  compatibility guard, including alias uniqueness. Malformed metadata fails
  even when added to an otherwise empty catalog.
- `routing_audit.py` and `trigger_audit.py` are static routing signals, not
  proof of semantic model routing. `trigger-cases.json` holds six
  representative requests per skill (direct, indirect, incomplete, negative,
  collision, edge); with an empty catalog the suite is empty, but a case that
  names an unknown skill or omits a field fails.

The plugin package identifier is `ega-skills` (short enough that every combined
`ega-skills:<skill>` identity fits the 64-character submission constraint); the
human-facing display name stays "egawilldoit skills".

`tests/` contains the remaining behavior tests for `preflight`/CI identity
helpers and the deterministic validators. They use standard-library `unittest`
and temporary git repositories; no unit test depends on live GitHub or on any
skill being present in the catalog.

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

Both PR jobs run the full gate sequence listed above. Exact-head validation and
merge-result validation are separate evidence classes and are never conflated:
a green `validate-merge` does not certify the PR head itself; only
`validate-head` does. Actions are pinned to immutable full commit SHAs
(`actions/checkout@11d5960a326750d5838078e36cf38b85af677262`,
`actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065`), and
validation dependencies are exact-pinned in `requirements-ci.txt`.

## Catalog

| Skill | Purpose | Origin | Ownership |
| --- | --- | --- | --- |
| _none_ | The active catalog is empty; add a row when adding a skill | — | — |

Catalog counts: 0 copied, 0 adapted, 0 original, 0 total.

Historical catalog tables and per-skill provenance remain in Git history and in
`THIRD_PARTY_NOTICES.md`; they are not active catalog entries.
