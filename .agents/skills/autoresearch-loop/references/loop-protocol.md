# Loop protocol

## Input contract
A run must have:
- goal
- scope
- metric name
- metric direction (`higher` or `lower`)
- explicit extractor definition
- verify command
- optional guard command
- stopping policy

## Preflight order
1. Load operating context.
2. Inspect repository state.
3. Inspect prior experiment memory.
4. Inspect code context.
5. Establish baseline.

Stop immediately if any of the required preflight steps fail.

## Isolation policy
- Clean git repo: create or use a dedicated run branch.
- Dirty git repo: create a dedicated worktree from current HEAD.
- Non-git repo: do not run the full loop; return a blocked-state report that explains why experiment commits and safe reverts are unavailable.

## Iteration protocol
For each iteration:
1. Re-read the target and prior results.
2. Pick one main hypothesis.
3. Edit only the files needed for that hypothesis.
4. Commit the experiment.
5. Run verify.
6. Parse the metric.
7. Run guard if configured.
8. Decide:
   - keep
   - discard
   - crash
   - inconclusive
9. Log the outcome.

## Keep criteria
Keep the experiment only if:
- the hypothesis matches the target
- verify succeeds
- the metric parses
- the metric improves, or the target explicitly allows non-regression for complexity/risk reduction
- guard passes if configured
- the change does not create disproportionate architectural damage

## Discard criteria
Discard when:
- verify fails
- metric parsing fails
- the metric regresses
- guard fails
- the change solves a different problem than the target
- risk exceeds value

## Stagnation policy
- reflect after 5 consecutive discard/crash/inconclusive outcomes
- hard stop after 10 consecutive failures unless the user explicitly wants deeper persistence

## Ambiguous verification
Treat ambiguous verification as blocked or inconclusive, never as success.
