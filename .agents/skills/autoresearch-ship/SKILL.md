---
name: autoresearch-ship
description: Prepare a release or deployment with checklist-first discipline and explicit approval boundaries. Use when the user wants readiness review, dry-run planning, rollback notes, or carefully approved execution steps.
---

# autoresearch-ship

Use this skill for release readiness, not for unapproved state changes.

## Modes
- checklist mode
- dry-run plan mode
- execute mode (only with explicit approval for every state-changing action)

## Workflow
1. Inspect current release inputs and quality gates.
2. Produce a checklist of missing prerequisites.
3. If requested, create a dry-run execution plan with rollback and monitoring notes.
4. Only execute push, merge, publish, deploy, or send actions with explicit user approval.

## Required outputs
- `artifacts/ship-checklist.md`
- optional `artifacts/release-plan.md`

## Rules
- checklist mode is the default
- separate preparation from execution
- do not infer permission for external side effects
- keep rollback and monitoring steps explicit

See also `references/ship-workflow.md`.
