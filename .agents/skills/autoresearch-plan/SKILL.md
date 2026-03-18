---
name: autoresearch-plan
description: Convert a user goal into a validated autoresearch target file. Use when the user wants Codex to define scope, metric, direction, verification, guard, and stopping rules before starting the loop.
---

# autoresearch-plan

Use this skill to turn a loose goal into a reusable target config.

## Workflow
1. Read `AGENTS.md`, the user request, and relevant repository context.
2. Infer likely scope, verification commands, and metric candidates from the repo.
3. Ask only for the missing required input.
4. Validate:
   - scope resolves to real files or intended globs
   - verify command is explicit and runnable in principle
   - metric direction is explicit
   - extractor is explicit (`regex`, `jsonpath`, or `script`)
   - guard command is optional but valid if present
5. Write the target to `.autoresearch/targets/<name>.yaml`.
6. Present a concise summary that the loop can consume without translation.

## Output contract
A valid target file must define:
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

## Rules
- prefer mechanical verification over subjective goals
- prefer narrow scope when confidence is low
- do not start the improvement loop from this skill unless the user asks for it
- if the repo is not in a shape where verify can be defined, stop with an actionable explanation

See also `references/plan-workflow.md`.
