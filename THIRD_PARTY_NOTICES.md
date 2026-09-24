# Third-party notices

This repository contains skills that are copied from, or adapted from, the
Cursor plugins repository. The remainder are original works.

## Upstream source

```text
repository:  https://github.com/cursor/plugins
commit:      12d587dfb20741cafc376c42c696c5f6e2a64487
license:     MIT
```

The exact source path, source commit, license, and import mode for every
imported or adapted skill is recorded in `upstream-sources.json`.

## Import modes

```text
copied    upstream methodology preserved; only packaging normalized
          (frontmatter, cross-skill references, directory placement)
adapted   studied upstream source, reimplemented platform-neutral
```

Copied skills are the work of the original authors listed below. No authorship
of unchanged upstream work is claimed here.

## Copied skills

From `pstack/skills/` (author: Lauren Tan):

```text
blast-radius
tdd
technical-writing
typescript-best-practices
unslop
principle-attack-the-premise
principle-boundary-discipline
principle-build-the-lever
principle-encode-lessons-in-structure
principle-exhaust-the-design-space
principle-experience-first
principle-fix-root-causes
principle-foundational-thinking
principle-guard-the-context-window
principle-laziness-protocol
principle-make-operations-idempotent
principle-migrate-callers-then-delete-legacy-apis
principle-minimize-reader-load
principle-model-the-domain
principle-outcome-oriented-execution
principle-prove-it-works
principle-redesign-from-first-principles
principle-separate-before-serializing-shared-state
principle-sequence-verifiable-units
principle-subtract-before-you-add
principle-test-behavior-not-implementation
principle-type-system-discipline
```

From `cursor-team-kit/skills/` (author: Eric Zakariasson):

```text
verify-this
run-smoke-tests
check-compiler-errors
get-pr-comments
fix-merge-conflicts
what-did-i-get-done
weekly-review
```

## Adapted skills

Adapted skills reuse the problem definition, workflow shape, and decision
rules of the upstream skill, but are reimplemented for a platform-neutral
Agent Skills runtime. The upstream skill and the new skill are recorded in
`upstream-sources.json`.

```text
understand-codebase                <- pstack/skills/how
recover-design-rationale           <- pstack/skills/why
design-architecture                <- pstack/skills/architect
compare-designs                    <- pstack/skills/arena
adversarial-review                 <- pstack/skills/interrogate
recover-work-context               <- pstack/skills/recall
work-retrospective                 <- pstack/skills/reflect
mine-work-patterns                 <- pstack/skills/automate-me + cursor-team-kit/skills/workflow-from-chats
record-evidence                    <- pstack/skills/show-me-your-work
create-verification-workflow       <- pstack/skills/create-verification-skill
maintain-verification-workflow     <- pstack/skills/maintain-verification-skill
parallelize-work                   <- pstack/skills/swarm
design-investigation               <- pstack/skills/figure-it-out
deliver-software                   <- pstack/skills/poteto-mode
verify-ui                          <- cursor-team-kit/skills/control-ui
verify-cli                         <- cursor-team-kit/skills/control-cli
review-and-ship                    <- cursor-team-kit/skills/review-and-ship
make-pr-easy-to-review             <- cursor-team-kit/skills/make-pr-easy-to-review
loop-on-ci                         <- cursor-team-kit/skills/loop-on-ci
fix-ci                             <- cursor-team-kit/skills/fix-ci
new-branch-and-pr                  <- cursor-team-kit/skills/new-branch-and-pr
deslop                             <- cursor-team-kit/skills/deslop
```

The six `cursor-team-kit` skills above were reclassified from copied to
adapted. Their upstream logic is preserved, but their GitHub access and base
branch handling were rewritten to be runtime-neutral: a native or connected
GitHub capability is preferred, the authenticated GitHub CLI is a fallback, and
the actual base branch is resolved instead of assuming `main`. Attribution to
the upstream authors is unchanged.

## Upstream license notices

### pstack

```text
MIT License

Copyright (c) 2026 Lauren Tan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### cursor-team-kit

```text
MIT License

Copyright (c) 2026 Cursor

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## This repository

This repository's own license is in `LICENSE`.
