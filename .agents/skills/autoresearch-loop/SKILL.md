---
name: autoresearch-loop
description: Run a disciplined autonomous improvement loop against a measurable metric. Use when the user wants one-change-per-iteration improvement with baseline, verification, keep/discard decisions, structured logging, and non-destructive rollback.
---

# autoresearch-loop

Use this skill to run the core autoresearch loop in a Codex-native way.

## Inputs
Prefer one of:
1. a validated target file under `.autoresearch/targets/*.yaml`
2. inline instructions that fully specify:
   - goal
   - scope
   - metric + direction
   - explicit metric extractor
   - verify command
   - optional guard command
   - stopping rule

If the inputs are incomplete, infer what you reasonably can from the repo and ask only for the missing required piece.

## Required preflight
Before the first change:
1. read `AGENTS.md`
2. load the active target or resolve the inline target
3. inspect repository state and git state
4. inspect prior runs and relevant code context
5. establish a baseline metric and write initial run state

If the repo is not a git repository and the requested task needs experiment commits or reverts, stop with a blocked summary instead of pretending the loop ran safely.

## Workflow
1. Create `.autoresearch/runs/<run-id>/`.
2. Snapshot the resolved target to `target.yaml`.
3. Record baseline details in `baseline.json`.
4. For each iteration:
   - choose one focused hypothesis
   - make one coherent change
   - commit it as `experiment: <short hypothesis>`
   - run verify
   - run guard if configured
   - keep only if verify passes, metric parses, metric improves or meets the allowed non-regression rule, and guard passes
   - otherwise discard with a non-destructive revert
   - append the result to `results.tsv`
5. Stop when the goal is met, the iteration cap is reached, or the run becomes blocked.
6. Write `summary.md` with the baseline, best result, kept experiments, discarded experiments, and next moves.

## Rules
- one coherent hypothesis per iteration
- never keep a change on ambiguous verification
- never revert unrelated user changes
- never use destructive git cleanup as routine discard behavior
- prefer a dedicated worktree when the repo starts dirty or risky
- prefer the simpler solution when outcomes are equivalent

## Artifacts
Always maintain these run artifacts:
- `target.yaml`
- `baseline.json`
- `results.tsv`
- `summary.md`
- `artifacts/`

See also:
- `references/core-principles.md`
- `references/loop-protocol.md`
- `references/results-logging.md`
