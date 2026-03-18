# Smoke checks

Run:

```bash
uv run python scripts/validate-codex-assets.py
uv run python -m unittest discover -s tests -v
python3 scripts/smoke/run.py
```

The smoke suite validates assets, runs the unit/integration tests, and then runs the fixture checks.
