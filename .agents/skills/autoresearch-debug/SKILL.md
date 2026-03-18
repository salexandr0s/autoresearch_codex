---
name: autoresearch-debug
description: Investigate a bug or failing behavior with an evidence-first workflow. Use when the user wants root-cause analysis, structured findings, reproducible evidence, and an optional handoff into autoresearch-fix.
---

# autoresearch-debug

Use this skill when behavior is wrong but the fix is not yet justified by evidence.

## Workflow
1. Capture the symptom, repro command, and current expectation.
2. Reproduce the issue or inspect existing evidence.
3. Narrow the likely cause with read-first investigation.
4. Run focused experiments only when they materially increase confidence.
5. Produce structured findings under the active run's `artifacts/` directory.
6. Recommend the smallest next fix hypothesis.

## Findings object
Each finding should include:
- `id`
- `symptom`
- `suspected_cause`
- `evidence`
- `confidence` (`low`, `medium`, `high`)
- `suggested_next_fix`

## Rules
- prefer evidence over intuition
- do not broaden the investigation without reason
- do not mutate unrelated files while debugging
- if no solid lead exists, say so explicitly

See also `references/debug-workflow.md`.
