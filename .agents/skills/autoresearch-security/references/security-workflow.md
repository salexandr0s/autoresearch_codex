# Security workflow

## Required outputs
Write both:
- `artifacts/security-findings.json`
- `artifacts/security-report.md`

## Review order
1. Clarify scope and assets.
2. Inspect inputs, trust boundaries, auth, secrets, data handling, and risky commands.
3. Record findings with evidence.
4. Recommend the smallest practical remediation path.

## Severity gating
If the user specifies `Fail on severity: <level>`, the review should clearly state whether any finding meets or exceeds that threshold.

## Auto-remediation
Allowed only on explicit opt-in. Even then, keep the remediation narrow, reviewable, and mechanically verified.
