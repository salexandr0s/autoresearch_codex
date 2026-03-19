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
