# Fix workflow

## Targeted categories
Common categories:
- test failures
- lint violations
- type errors
- build failures

## Keep rule
A fix is worth keeping only when:
- the targeted error count decreases
- verify completes
- the change does not introduce a new blocker
- guard passes if configured

## Handoff from debug
If debug findings exist, read them first and use the highest-confidence finding as the next fix hypothesis.
