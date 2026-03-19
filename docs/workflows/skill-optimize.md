# autoresearch skill-optimize

Use `autoresearch skill-optimize` to optimize a target `SKILL.md` with runner-backed test inputs and binary evals.

```bash
uv run autoresearch skill-optimize \
  --skill .agents/skills/my-skill/SKILL.md \
  --inputs-file path/to/inputs.yaml \
  --evals-file path/to/evals.yaml \
  --runs-per-experiment 5
```

The command:
- validates the skill and datasets
- writes a reusable target file under `.autoresearch/targets/`
- captures a baseline before mutation
- reuses the normal keep/discard loop
- writes scored output artifacts under the run directory

## v1 scoring model

`skill-optimize` uses Codex twice during verify:

- once to execute the current skill against each input
- once to judge each run against the configured binary evals

This is intentionally thin for v1: the runner still owns isolation, artifacts, baseline capture, keep/discard, and metric parsing.

## How scoring stays bounded

- each sample runs in an isolated temp workspace
- only bounded repo assets are copied into that workspace
- the judge sees the final response plus changed-file snapshots
- judge output must match the JSON schema exactly
- ambiguous judge output fails verification instead of counting as success

The judge prompt treats candidate output and changed files as untrusted evidence, not instructions.

## Intended operating envelope

Use small, crisp binary eval suites. Prefer evals that can be answered directly from the final response and any changed-file evidence.

`--runs-per-experiment` reduces noise by replaying the same input multiple times, but it does not provide strong statistical guarantees.

Changed-file content and the total eval bundle may be truncated in artifacts and prompts. When that happens, the truncation is marked explicitly so scoring remains explainable.
