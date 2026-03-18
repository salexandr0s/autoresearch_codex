# Ship workflow

## Checklist mode
Use when the user wants readiness only. Cover:
- current branch and diff state
- tests / lint / typecheck / build readiness
- release notes or changelog readiness
- rollback plan presence
- monitoring plan presence

## Dry-run plan mode
Add:
- ordered execution steps
- approval boundaries
- rollback notes
- monitor/watch items after release

## Execute mode
Only allowed when the user clearly approves the state-changing actions. Approval for one action does not imply approval for all later actions.
