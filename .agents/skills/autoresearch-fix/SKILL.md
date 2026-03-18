---
name: autoresearch-fix
description: Reduce a concrete error count with one-fix-per-iteration discipline. Use when the user wants to address failing tests, lint, type, or build errors while keeping only changes that measurably reduce the target error set.
---

# autoresearch-fix

Use this skill to reduce a known class of failure.

## Inputs
Prefer one of:
1. an active debug findings artifact
2. a clear error category and verify command

## Workflow
1. Establish the baseline error count.
2. Choose one fix hypothesis.
3. Make one coherent fix.
4. Run verify and re-count the target errors.
5. Keep the change only if the error count decreases and guard passes if configured.
6. Discard with a non-destructive revert if the count does not improve.
7. Log the result in the active run directory.

## Rules
- one fix hypothesis per iteration
- do not mix unrelated fixes
- preserve the loop's keep/discard discipline
- default to the latest debug findings when the user says to continue from debugging

See also `references/fix-workflow.md`.
