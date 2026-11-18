# Contributing to the skills catalog

This catalog holds 66 self-contained agent skills published as the `ega-skills`
plugin. Agents working here follow [AGENTS.md](AGENTS.md); this guide is the
human companion for proposing a skill.

## Adding a skill

1. Create `skills/<skill-name>/` — kebab-case, matching
   `^[a-z0-9]+(-[a-z0-9]+)*$`, identical to the `name` in frontmatter.
2. Write `SKILL.md` with YAML frontmatter containing ONLY `name` and
   `description`. The description is the routing surface: include the trigger
   phrases someone would actually say, plus when NOT to use the skill and which
   neighboring skill owns the adjacent job.
3. Add `ega.yaml` with trigger phrases for EGA routing.
4. Add `agents/openai.yaml`, or generate it with `scripts/sync_openai_yaml.py`.
5. Put deep material in `references/` (rubrics, schemas, contracts). If the
   skill uses the shared vocabulary, copy `references/operating-contract.md`
   in rather than redefining terms.
6. Bundle deterministic checks in `scripts/` where a script beats prose.

## Before opening a PR

- `python3 -m pip install --disable-pip-version-check -r requirements-ci.txt`
- Run the full gate sequence in [AGENTS.md](AGENTS.md#validation) — all green.
- One skill per PR. Describe what it does, when to use it, and the gates
  you ran.

## Boundaries

- Never commit secrets or credentials.
- Never hand-edit files owned by a sync script; fix the source and re-run it.
- Never weaken a validator to make a failing skill pass.
- Never float a pinned dependency in `requirements-ci.txt`.
