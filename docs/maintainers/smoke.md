# Smoke checks

Run both:

```bash
python3 scripts/validate-codex-assets.py
python3 scripts/smoke/run.py
```

The smoke suite:
- validates the repository structure
- initializes temporary git repos for fixtures that require git
- runs fixture verify commands when defined
- checks dirty-worktree scenarios where declared
