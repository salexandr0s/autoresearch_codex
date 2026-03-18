# Contributing

## Source of truth

This repo is Codex-first.

Canonical surfaces:
- `AGENTS.md`
- `.codex/config.toml`
- `.agents/skills/`
- `.autoresearch/targets/`
- `docs/`
- `scripts/`

Do not treat bootstrap material or any future legacy compatibility bundle as the source of truth.

## Workflow for changes

1. Read `AGENTS.md`.
2. Keep the change small and coherent.
3. Update docs when behavior changes.
4. Run validation.
5. Run smoke checks when you change structure, docs, targets, or scripts.

## Adding or changing a skill

1. Create or edit `.agents/skills/<skill-name>/SKILL.md`.
2. Keep durable repo-wide behavior in `AGENTS.md`, not in the skill body.
3. Add `references/` docs only when they reduce ambiguity.
4. Update `docs/workflows/`.
5. Run:

```bash
python3 scripts/validate-codex-assets.py
python3 scripts/smoke/run.py
```

## Target file contract

Target files live under `.autoresearch/targets/` and must define:
- `name`
- `goal`
- `scope.include`
- optional `scope.exclude`
- `metric.name`
- `metric.direction`
- `metric.extractor.type`
- `metric.extractor.value`
- `verify.command`
- optional `guard.command`
- `stopping.max_iterations`
- `stopping.stagnation_reflect_after`
- `stopping.stop_after_consecutive_failures`

## Release flow

See `docs/maintainers/release.md`.
