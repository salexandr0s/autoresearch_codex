# autoresearch fix

Use `autoresearch fix` to run the loop with an error-reduction target.

```bash
uv run autoresearch fix --target .autoresearch/targets/default.yaml
```

If recent debug findings exist, the runner automatically includes them as context.
