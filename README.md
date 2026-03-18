# autoresearch_codex

A Codex-first adaptation of the `autoresearch` workflow: one focused change per iteration, mechanical verification, git-backed experiment memory, safe keep/discard decisions, and durable run logs.

## What ships in v2

Primary workflows:
- `autoresearch-plan`
- `autoresearch-loop`
- `autoresearch-debug`
- `autoresearch-fix`
- `autoresearch-security`
- `autoresearch-ship`

Deferred for a later release:
- `autoresearch-scenario`
- `autoresearch-predict`

## Repository layout

- `AGENTS.md` — permanent operating doctrine
- `.codex/config.toml` — minimal project defaults
- `.agents/skills/` — Codex-native workflows
- `.autoresearch/targets/` — reusable run targets
- `.autoresearch/runs/` — per-run state and artifacts
- `docs/` — canonical documentation
- `scripts/` — validation, smoke, and release helpers
- `test-fixtures/` — deterministic sample repos for smoke checks

## Quick start

1. Open the repo in Codex so `AGENTS.md` and `.codex/config.toml` load.
2. Review `docs/getting-started.md`.
3. Create or refine a target with `autoresearch-plan`.
4. Run `autoresearch-loop` against that target.
5. Inspect `.autoresearch/runs/<run-id>/` and the experiment branch/worktree.

### Example prompt shape

```text
Goal: Reduce failing tests in the parser package.
Context: The parser tests fail intermittently after the recent tokenizer change.
Constraints: Keep the change inside src/parser and tests/parser. Do not add dependencies.
Done when: A reusable target exists with verify and guard commands that I can run with autoresearch-loop.
```

## Important runtime expectations

- The full loop expects a git repository.
- Dirty repositories should use worktree isolation.
- Ambiguous metrics are treated as blocked, not success.
- The system never treats destructive git cleanup as a normal discard path.

## Validation

```bash
python3 scripts/validate-codex-assets.py
python3 scripts/smoke/run.py
```

## Docs

Start with `docs/index.md`.
