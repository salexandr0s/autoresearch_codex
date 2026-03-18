# autoresearch-security

Use this workflow for read-first security review.

## Default posture
Read-only unless the user explicitly opts into remediation.

## Output artifacts
- `artifacts/security-findings.json`
- `artifacts/security-report.md`

## Severity gating
Use `Fail on severity: <level>` when the user wants a thresholded result.
