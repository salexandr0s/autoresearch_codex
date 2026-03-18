# autoresearch loop

Use `autoresearch loop` to run the keep/discard experiment cycle.

## Example

```bash
uv run autoresearch loop --target .autoresearch/targets/default.yaml
```

The runner handles:
- baseline
- dedicated worktree/branch
- one experiment commit per iteration
- verify and optional guard
- revert-based discard
- results logging
- summary generation

Use `--unbounded` for a long-running unattended session.
