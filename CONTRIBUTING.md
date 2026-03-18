# Contributing

## Source of truth

This repo is runner-backed and Codex-first.

Canonical surfaces:
- `AGENTS.md`
- `.agents/skills/`
- `.autoresearch/targets/`
- `src/autoresearch/`
- `docs/`
- `scripts/`
- `tests/`

## Development setup

```bash
uv sync
```

## Required checks

```bash
uv run python scripts/validate-codex-assets.py
uv run python -m unittest discover -s tests -v
python3 scripts/smoke/run.py
bash scripts/release.sh --dry-run
```

## Making changes

1. Keep the change coherent.
2. Keep durable behavior in `AGENTS.md`.
3. Keep workflow prompting in `.agents/skills/`.
4. Keep runner behavior in `src/autoresearch/`.
5. Update docs when behavior changes.

## Adding or changing a workflow

- update the skill under `.agents/skills/`
- update the runtime adapter in `src/autoresearch/`
- update docs in `docs/workflows/`
- add tests

## Release flow

See `docs/maintainers/release.md`.
