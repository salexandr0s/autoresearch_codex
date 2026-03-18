# autoresearch_codex

A runner-backed, Codex-first adaptation of `autoresearch` for repository work.

Like `karpathy/autoresearch`, the core idea is the same:
- establish a baseline
- let the agent try one hypothesis at a time
- verify mechanically
- keep or discard
- log everything
- repeat

The difference is that this repo generalizes the pattern from a single-file ML training repo to **scoped repository workflows** with reusable skills:
- `plan`
- `loop`
- `debug`
- `fix`
- `security`
- `ship`

## What this now includes

- a real Python runner and CLI: `autoresearch`
- Codex CLI integration via `codex exec`
- dedicated run branches + worktrees
- per-run logs under `.autoresearch/runs/<run-id>/`
- target files under `.autoresearch/targets/*.yaml`
- repo-local skills under `.agents/skills/`
- validation, tests, smoke checks, and release dry-run support

## Install

Requirements:
- Python 3.11+
- `uv`
- Codex CLI (`codex`)
- a git repository to run experiments against

```bash
uv sync
```

## Quick start

### 1. Validate the scaffold and Codex runtime

```bash
uv run autoresearch validate
```

### 2. Create or update a target

```bash
uv run autoresearch plan \
  --goal "Reduce failing parser tests" \
  --context "Recent tokenizer changes caused regressions" \
  --constraints "Stay within src/parser and tests/parser" \
  --done-when "A reusable target exists for the loop"
```

### 3. Run the loop

```bash
uv run autoresearch loop --target .autoresearch/targets/default.yaml
```

### 4. Inspect the run

Look at:
- `.autoresearch/runs/<run-id>/summary.md`
- `.autoresearch/runs/<run-id>/results.tsv`
- `.autoresearch/runs/<run-id>/engine.json`
- the dedicated `autoresearch/<workflow>/<run-id>` branch

## Main commands

```bash
uv run autoresearch validate
uv run autoresearch plan --goal "..."
uv run autoresearch loop --target .autoresearch/targets/default.yaml
uv run autoresearch debug --summary "Investigate flaky parser behavior"
uv run autoresearch fix --target .autoresearch/targets/default.yaml
uv run autoresearch security
uv run autoresearch ship
uv run autoresearch resume --run-id <run-id>
```

## Runtime model

The runner owns the outer loop:
- git/worktree setup
- baseline
- verify/guard execution
- metric parsing
- keep/discard decisions
- run logging
- resume

Codex owns the bounded inner task:
- produce one target
- make one scoped change
- or write one structured report

## Repo layout

- `AGENTS.md` — permanent doctrine
- `.agents/skills/` — workflow prompts
- `.autoresearch/targets/` — reusable targets
- `.autoresearch/runs/` — run state and logs
- `src/autoresearch/` — runtime package
- `tests/` — unit + integration tests
- `scripts/` — validation, smoke, release helpers

## Verification

```bash
uv run python scripts/validate-codex-assets.py
uv run python -m unittest discover -s tests -v
python3 scripts/smoke/run.py
bash scripts/release.sh --dry-run
```

## Notes

- The default mode is bounded; use `--unbounded` for overnight runs.
- The runner uses revert-based discard on experiment commits.
- Manual skill-only use is still possible, but the runner-backed flow is now the primary path.

See `docs/index.md` for the full docs set.
