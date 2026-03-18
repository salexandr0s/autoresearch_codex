# Release flow

## Principles
- Codex-first assets are canonical.
- Release validation must pass before packaging.
- A compatibility bundle is optional and never the default source of truth.

## Dry-run

```bash
bash scripts/release.sh --dry-run
```

## Package a release bundle

```bash
bash scripts/release.sh dist/release
```

The release script validates the repo first, then stages a clean bundle with the Codex-first assets.
