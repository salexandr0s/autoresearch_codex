# Getting started

## 1. Open the repo in Codex

The repo is designed to load:
- `AGENTS.md`
- `.codex/config.toml`
- `.agents/skills/`

## 2. Use the planning flow first

Start with `autoresearch-plan` unless you already have a valid target file.

Recommended prompt shape:
- Goal:
- Context:
- Constraints:
- Done when:

## 3. Save a reusable target

Place reusable targets under `.autoresearch/targets/`.

Example fields:
- goal
- scope.include
- metric.name
- metric.direction
- metric.extractor
- verify.command
- optional guard.command
- stopping rules

## 4. Run the loop

Use `autoresearch-loop` with the saved target.

Expected run artifacts:
- `target.yaml`
- `baseline.json`
- `results.tsv`
- `summary.md`
- `artifacts/`

## 5. Inspect the result

Review:
- the run summary
- the experiment branch or worktree
- kept and discarded hypotheses

## Notes

- The full loop expects a git repository.
- If the repo starts dirty, use worktree isolation.
- If metric extraction is ambiguous, fix the target before continuing.
