---
name: autoresearch-security
description: Perform a read-first security review with structured findings and explicit severity gating. Use when the user wants evidence-backed risks, remediation guidance, and optional opt-in auto-remediation.
---

# autoresearch-security

Use this skill to review security posture without defaulting to unsafe automated changes.

## Default mode
Read-only by default.

## Workflow
1. Define the review scope.
2. Inspect code, config, docs, and known trust boundaries.
3. Record evidence-backed findings.
4. Classify each finding by severity and likelihood.
5. Produce a concise report with remediation guidance.
6. Perform auto-remediation only if the user explicitly opts in.

## Findings object
Each security finding should include:
- `id`
- `title`
- `severity`
- `affected_surface`
- `evidence`
- `impact`
- `recommended_remediation`

## Rules
- default to read-only
- do not claim a vulnerability without evidence
- use `Fail on severity:` as the runtime-neutral threshold when the user wants gating
- do not deploy or publish any remediation

See also `references/security-workflow.md`.
