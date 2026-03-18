# autoresearch plan

Use `autoresearch plan` to turn a goal into a validated target YAML file.

## Example

```bash
uv run autoresearch plan \
  --goal "Reduce failing parser tests" \
  --context "Tokenizer changes caused regressions" \
  --constraints "Stay inside src/parser and tests/parser" \
  --done-when "A reusable target exists"
```

The runner asks Codex for one YAML target, validates it, and saves it under `.autoresearch/targets/`.
