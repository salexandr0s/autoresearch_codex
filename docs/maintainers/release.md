# Release flow

## Validate first

```bash
python3 scripts/scan-secrets.py
uv run python scripts/validate-codex-assets.py
uv run python -m unittest discover -s tests -v
python3 scripts/smoke/run.py
```

## Dry-run the release bundle

```bash
bash scripts/release.sh --dry-run
```

## Stage a release bundle

```bash
bash scripts/release.sh dist/release
```

Release output paths must stay under `dist/`; absolute or traversal paths are rejected.

The release bundle now includes the runtime package, tests, docs, and Codex-first scaffold.
