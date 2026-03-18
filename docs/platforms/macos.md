# macOS guide

`autoresearch_codex` already works on macOS for normal repo workflows. This guide makes the path explicit.

## Support level

- **Apple Silicon (`darwin` + `arm64`)** — first-class path for generic repo work and the best path for Karpathy-style local ML loops
- **Intel Mac** — supported for generic repo workflows, but not a first-class path for Apple Silicon / MPS ML examples

## What this repo does vs what the target repo must do

`autoresearch_codex` is the **outer loop runner**. It:
- creates run branches and worktrees
- calls Codex for one bounded task at a time
- runs verify and optional guard commands
- keeps or reverts experiments
- logs run artifacts

The **target repo** owns workload portability. If a training repo needs Apple Silicon / MPS changes, those changes belong in the target repo, like [`autoresearch-macos`](../examples/autoresearch-macos.md) does for Karpathy's original training setup.

This repo does **not** automatically make CUDA-only training code run on MPS.

## Required tools

- `git`
- `uv`
- Python 3.11+
- Codex CLI (`codex`)

## Optional but recommended

- Xcode Command Line Tools
- PyTorch with MPS support for Apple Silicon ML targets
- `caffeinate` for overnight runs

## First command to run

```bash
uv run autoresearch validate
```

On macOS, `validate` now reports:
- OS + architecture
- whether Apple Silicon was detected
- `git` / `uv` / `codex` / `caffeinate`
- Xcode Command Line Tools status
- optional torch + MPS facts when torch is importable
- whether generic repo workflows and Apple Silicon ML workflows look supported

## Overnight usage

For a bounded or unbounded overnight run on a Mac:

```bash
caffeinate -dimsu uv run autoresearch loop --target .autoresearch/targets/default.yaml
```

## Notes and limitations

- Mutation workflows still expect a git repo.
- `peak_vram_mb` can be useful as a diagnostic, but it is usually a weak acceptance metric on Apple Silicon because unified-memory reporting is repo-specific.
- If `validate` warns about CUDA-specific assumptions, fix those in the target repo, not in `autoresearch_codex`.
