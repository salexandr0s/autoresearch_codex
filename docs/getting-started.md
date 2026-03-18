# Getting started

## 1. Install dependencies

```bash
uv sync
```

## 2. Validate the repo and Codex CLI

```bash
uv run autoresearch validate
```

## 3. Create a target

```bash
uv run autoresearch plan \
  --goal "Reduce failing parser tests" \
  --context "Tokenizer changes introduced regressions" \
  --constraints "Stay within src/parser and tests/parser" \
  --done-when "The loop has a valid target file"
```

## 4. Run the loop

```bash
uv run autoresearch loop --target .autoresearch/targets/default.yaml
```

## 5. Resume if needed

```bash
uv run autoresearch resume --run-id <run-id>
```

## 6. Inspect artifacts

Each run creates:
- `target.yaml`
- `baseline.json`
- `results.tsv`
- `summary.md`
- `engine.json`
- `iterations/<n>/...`

## Notes

- The runner expects a git repo.
- The runner uses a dedicated worktree and branch.
- Bounded mode is the default.
- `--unbounded` is the explicit overnight mode.
