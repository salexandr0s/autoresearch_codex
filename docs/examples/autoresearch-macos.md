# Using `autoresearch_codex` with an `autoresearch-macos`-style repo

This is the closest macOS analogue to Andrej Karpathy's original `autoresearch` workflow:
- one main training file
- one mechanical metric
- one bounded experiment at a time
- keep or discard based on that metric

## 1. Validate your Mac first

```bash
uv run autoresearch validate
```

On Apple Silicon, you want `generic repo workflows: supported` and ideally `Apple Silicon ML workflows: supported` or at least `best-effort`.

## 2. Point the runner at the training repo

```bash
uv run autoresearch plan \
  --repo /path/to/autoresearch-macos \
  --goal "Lower val_bpb in the training loop" \
  --target-name macos-train
```

For repos shaped like:
- `train.py`
- `prepare.py`
- `program.md`

`plan` now tries to infer a Karpathy-style target:
- scope: `train.py`
- verify: `uv run train.py`
- metric: `val_bpb`
- direction: `lower`

## 3. Or start from the shipped example target

See [`examples/macos/karpathy-train-loop.yaml`](../../examples/macos/karpathy-train-loop.yaml).

## 4. Run the loop

```bash
uv run autoresearch loop \
  --repo /path/to/autoresearch-macos \
  --target /path/to/autoresearch-macos/.autoresearch/targets/macos-train.yaml
```

## 5. Inspect the result

Look at:
- `.autoresearch/runs/<run-id>/summary.md`
- `.autoresearch/runs/<run-id>/results.tsv`
- `.autoresearch/runs/<run-id>/engine.json`
- the `autoresearch/loop/<run-id>` branch

## 6. Overnight on macOS

```bash
caffeinate -dimsu uv run autoresearch loop \
  --repo /path/to/autoresearch-macos \
  --target /path/to/autoresearch-macos/.autoresearch/targets/macos-train.yaml
```

## Important boundary

If the training repo still assumes CUDA, FlashAttention, or NVIDIA-only memory reporting, the fix belongs in the **target repo**. That is exactly what `autoresearch-macos` demonstrates.
