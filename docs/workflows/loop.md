# autoresearch-loop

Use this workflow to run the disciplined improvement loop.

## Preflight
1. load target and repo context
2. inspect git state
3. inspect prior run memory
4. inspect code context
5. establish baseline

## Run behavior
- one hypothesis per iteration
- commit before verify
- keep only verified improvements
- discard failed experiments with a non-destructive revert
- log every iteration outcome in `results.tsv`

## Run artifacts
- `target.yaml`
- `baseline.json`
- `results.tsv`
- `summary.md`
- `artifacts/`
