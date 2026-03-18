# Getting started

## 1. Install dependencies

```bash
uv sync
```

## 2. Validate the repo and Codex CLI

```bash
uv run autoresearch validate
```

On macOS, `validate` also reports Apple Silicon, Xcode CLT, `caffeinate`, and optional torch/MPS status. See the [macOS guide](platforms/macos.md).

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
- For Karpathy-style local ML repos on Mac, this runner owns the outer loop; target-repo MPS/CUDA portability stays in the target repo.
