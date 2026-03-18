# Results logging

Each run lives under `.autoresearch/runs/<run-id>/`.

## Required files
- `target.yaml` — resolved snapshot of the exact run target
- `baseline.json` — preflight and baseline state
- `results.tsv` — append-only iteration log
- `summary.md` — human-readable run summary
- `artifacts/` — workflow-specific evidence and reports

## `baseline.json`
Record at least:
- run id and timestamp
- repo root
- whether the repo is a git repository
- branch and HEAD if available
- whether the starting worktree is dirty
- isolation mode (`in_place`, `branch`, or `worktree`)
- verify command
- guard command if present
- parsed baseline metric
- parse status

## `results.tsv`
Use this exact header:

```text
iteration\ttimestamp\tbranch\tcommit\trevert_commit\tmetric\tbest_metric\tdelta_from_best\tverify_status\tguard_status\tdecision\thypothesis\tfiles_touched\tartifact_path\tdecision_reason
```

## `summary.md`
Always include:
- goal
- baseline metric
- best metric
- kept experiments
- discarded experiments
- whether guard stayed green
- final stop reason
- recommended next moves
