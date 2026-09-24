---
name: check-compiler-errors
description: "Run the repository's compile and type-check commands, summarize failures by file and category, and fix the highest-confidence issues first. Use after edits, when a build or type-check breaks, or before sending a branch to review."
---

# Check compiler errors

## Trigger

Compile or type-check failures are blocking local validation or CI.

## Workflow

1. Run the repo's compile and type-check commands.
2. Summarize errors by file and type.
3. Fix the highest-confidence issues first.
4. Re-run checks until clean or blocked.

## Output

- Current compile and type-check status
- Error summary grouped by file and category
- Fixes applied and remaining blockers
