# autoresearch_codex

`autoresearch_codex` is a **runner-backed, Codex-native adaptation** of [Andrej Karpathy's `autoresearch`](https://github.com/karpathy/autoresearch), generalized from a narrow single-program optimization loop into a **repo-oriented improvement system**.

The original `autoresearch` idea is simple and powerful:
- establish a baseline
- try one hypothesis at a time
- verify mechanically
- keep or discard
- log what happened
- repeat

This repo keeps that core loop, but adapts it for **real repositories** and for **Codex** instead of Claude-centric promptware.

## What this can do

This repo now ships a real CLI runner:

```bash
autoresearch
```

with these workflows:

- `plan` — draft a validated target file for a measurable repo objective
- `loop` — run the real keep/discard improvement loop against a target
- `debug` — produce structured findings for a concrete issue
- `fix` — run an error-reduction loop
- `security` — produce a read-first security review, with optional remediation mode
- `ship` — produce a release-readiness checklist and dry-run plan
- `resume` — continue a prior iterative run
- `validate` — verify scaffold + runtime prerequisites

## What makes it different from Karpathy's original project

Karpathy's original project is the direct inspiration, but this repo changes the operating model in a few important ways:

- it is **repo-oriented**, not focused on one training/program file
- it uses **Codex CLI** as the backend
- it supports reusable **target files** under `.autoresearch/targets/`
- it creates structured **run artifacts** under `.autoresearch/runs/<run-id>/`
- it uses dedicated **run branches and worktrees**
- it uses **revert-based discard**, not destructive history rewriting
- it supports multiple bounded workflows beyond the core optimization loop

## What is verified today

Verified in this repo:
- real `plan` runs with structured output
- real `loop` runs with experiment commits, verification, and keep/discard decisions
- real `fix` runs with metric reduction
- real `ship` runs with structured checklist output
- `debug` / `security` produce structured artifacts and bounded fallback when needed
- validation, unit tests, smoke tests, and release dry-run all pass

## Safety model

The runner owns the outer loop:
- git/worktree setup
- baseline capture
- verify/guard execution
- metric parsing
- keep/discard decisions
- logging and summaries
- resume behavior

Codex owns only the bounded inner task:
- produce one target
- make one scoped experiment
- or produce one structured report

By default this tool does **not** push, merge, publish, deploy, rotate secrets, or perform destructive git cleanup.

## Repo layout

- `AGENTS.md` — permanent operating doctrine
- `.agents/skills/` — Codex workflow skills
- `.autoresearch/targets/` — reusable targets
- `.autoresearch/runs/` — per-run state and artifacts
- `src/autoresearch/` — runtime package
- `tests/` — unit + integration tests
- `scripts/` — validation, smoke, and release helpers
- `docs/` — user and maintainer docs

## Install

Requirements:
- Python 3.11+
- `uv`
- Codex CLI (`codex`)
- a git repository for mutation workflows

Setup:

```bash
uv sync
```

## Quick start

### 1. Validate the scaffold and Codex CLI

```bash
uv run autoresearch validate
```

### 2. Create a target

```bash
uv run autoresearch plan \
  --goal "Reduce failing parser tests" \
  --context "Recent tokenizer changes caused regressions" \
  --constraints "Stay within src/parser and tests/parser" \
  --done-when "Create a reusable target for the loop"
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
- `.autoresearch/runs/<run-id>/iterations/<n>/...`
- the `autoresearch/<workflow>/<run-id>` branch

## Main commands

```bash
uv run autoresearch validate
uv run autoresearch plan --goal "..."
uv run autoresearch loop --target .autoresearch/targets/default.yaml
uv run autoresearch debug --summary "Investigate flaky parser behavior"
uv run autoresearch fix --target .autoresearch/targets/default.yaml
uv run autoresearch security --summary "Review the repo for security risks"
uv run autoresearch ship --summary "Prepare a release-readiness checklist"
uv run autoresearch resume --run-id <run-id>
```

## Verification

```bash
uv run autoresearch validate --target .autoresearch/targets/live-dogfood-tests.yaml
uv run python -m unittest discover -s tests -v
python3 scripts/smoke/run.py
bash scripts/release.sh --dry-run
```

## Notes

- bounded mode is the default
- `--unbounded` is the explicit long-running mode
- mutation workflows require git
- report workflows prefer bounded context and may fall back cleanly on timeout
- manual skill-only usage is still possible, but the runner-backed path is the primary mode

See `docs/index.md` for the full docs set.
