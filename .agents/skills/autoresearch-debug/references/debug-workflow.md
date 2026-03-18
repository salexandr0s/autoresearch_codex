# Debug workflow

## Objective
Turn an observed failure into a concise, evidence-backed diagnosis.

## Required outputs
Write both:
- `artifacts/findings.json`
- `artifacts/findings.md`

## Investigation order
1. Re-state the failure and expected behavior.
2. Establish or inspect a repro path.
3. Collect the smallest set of evidence that distinguishes plausible causes.
4. Rank likely causes.
5. Recommend one fixable next step.

## Stop conditions
Stop when:
- a high-confidence root cause exists
- the issue is not reproducible with current information
- the environment blocks further useful investigation
