from __future__ import annotations

from .models import EngineState, TargetConfig, Workflow


WORKFLOW_LABELS: dict[Workflow, str] = {
    "plan": "target-planning",
    "loop": "improvement-loop",
    "skill-optimize": "skill-optimization-loop",
    "debug": "repo-investigation",
    "fix": "error-reduction-loop",
    "security": "risk-review",
    "ship": "release-readiness",
}


DOCTRINE_DIGEST = """
RUNTIME DOCTRINE
- Read before write.
- One coherent hypothesis per iteration when mutation is allowed.
- Verification is mechanical; do not claim success without it.
- The runner owns git, worktrees, verification, logging, and keep/discard.
- Stay inside the provided scope and context.
- If critical information is missing, say so briefly instead of guessing.
""".strip()


ITERATION_BRIEF = """
ITERATION CONTRACT
- You are in a real editable worktree.
- Do not run git commands.
- Do not touch `.autoresearch/runs/`, engine metadata, or the autoresearch runtime unless explicitly in scope.
- Make exactly one coherent change.
- End your final message with:
  Hypothesis: <one-line hypothesis>
  Summary: <short summary>
""".strip()


SKILL_OPTIMIZE_BRIEF = """
SKILL OPTIMIZE CONTRACT
- The primary target is a SKILL.md workflow, not the autoresearch runtime.
- Preserve valid frontmatter and markdown structure.
- Prefer one focused instruction change over broad rewrites.
- Touch references/examples only if they are explicitly in scope and required by the same hypothesis.
""".strip()


PLAN_BRIEF = """
PLAN CONTRACT
- You are running in a bounded context workspace, not the full repository.
- Use only `summary.md`, `manifest.json`, and files under `files/`.
- Do not perform broad repo discovery.
- Do not run shell commands, tests, or extra file-discovery commands.
- Do not open files other than the bounded `files/` tree.
- Do not call MCP tools or create a todo list.
- Return the final JSON immediately once you have enough information.
- Return only JSON matching the provided schema.
- Choose conservative, mechanically verifiable defaults.
""".strip()


REPORT_BRIEFS: dict[Workflow, str] = {
    "debug": """
DEBUG CONTRACT
- Investigate the request using the bounded context workspace only.
- Prefer evidence and likely failure modes over speculation.
- No code changes are allowed.
- You may read copied files under `files/` if needed.
- Do not run tests or broad file-discovery commands.
- Do not call MCP tools or create a todo list.
- Return the final JSON immediately once you have enough information.
- Return JSON matching the provided schema.
- Keep the response short: 3-7 findings max.
""".strip(),
    "security": """
SECURITY CONTRACT
- Review the bounded context workspace only.
- Focus on subprocesses, secrets, auth, dependency, and configuration risk.
- No code changes are allowed.
- You may read copied files under `files/` if needed.
- Do not run tests or broad file-discovery commands.
- Do not call MCP tools or create a todo list.
- Return the final JSON immediately once you have enough information.
- Return JSON matching the provided schema.
- Keep the response short: 3-7 findings max.
""".strip(),
    "ship": """
SHIP CONTRACT
- Produce a release-readiness or dry-run shipping artifact from the bounded context workspace only.
- No pushes, publishes, deploys, merges, or external side effects.
- Do not run shell commands, tests, or extra file-discovery commands.
- Do not attempt mechanical verification from the context workspace; use provided metadata only.
- Do not call MCP tools or create a todo list.
- Return the final JSON immediately once you have enough information.
- Return JSON matching the provided schema.
- Keep the answer concise: a short checklist and a short release plan only.
    """.strip(),
    "plan": PLAN_BRIEF,
    "loop": ITERATION_BRIEF,
    "skill-optimize": ITERATION_BRIEF,
    "fix": ITERATION_BRIEF,
}


def build_iteration_prompt(
    *,
    workflow: Workflow,
    target: TargetConfig,
    engine: EngineState,
    iteration: int,
    baseline_metric: float,
    best_metric: float,
    recent_results: str,
    reflection_mode: bool,
    findings_text: str | None = None,
) -> str:
    reflection_note = (
        "Reflection mode is ON because recent iterations did not improve. Re-read nearby code and try a meaningfully different hypothesis."
        if reflection_mode
        else "Reflection mode is OFF."
    )
    workflow_brief = f"\n\n{SKILL_OPTIMIZE_BRIEF}" if workflow == "skill-optimize" else ""
    findings_section = f"\nRelevant findings:\n{findings_text.strip()}\n" if findings_text else ""
    return f"""
WORKFLOW: {workflow}
ITERATION: {iteration}
TARGET NAME: {target.name}
GOAL: {target.goal}
BASELINE METRIC: {baseline_metric:.6f}
BEST METRIC SO FAR: {best_metric:.6f}
SCOPE INCLUDE: {', '.join(target.scope.include)}
SCOPE EXCLUDE: {', '.join(target.scope.exclude) or '(none)'}
METRIC NAME: {target.metric.name}
METRIC DIRECTION: {target.metric.direction}
VERIFY COMMAND: {target.verify.command}
GUARD COMMAND: {target.guard.command if target.guard else '(none)'}
RUN BRANCH: {engine.run_branch}
{reflection_note}

Recent results:
{recent_results or '(none yet)'}
{findings_section}
{DOCTRINE_DIGEST}

{ITERATION_BRIEF}
{workflow_brief}
""".strip() + "\n"


def build_plan_prompt(
    *,
    target_name: str,
    goal: str,
    context: str,
    constraints: str,
    done_when: str,
    context_summary: str,
) -> str:
    return f"""
WORKFLOW: {WORKFLOW_LABELS['plan']}
TARGET NAME: {target_name}
GOAL: {goal}
USER CONTEXT: {context or '(none provided)'}
CONSTRAINTS: {constraints or '(none provided)'}
DONE WHEN: {done_when or '(none provided)'}

{DOCTRINE_DIGEST}

{PLAN_BRIEF}

CONTEXT SUMMARY
{context_summary.strip()}

Return only JSON that matches the output schema.
No shell commands. No tool-driven repo exploration.
""".strip() + "\n"


def build_report_prompt(
    *,
    workflow: Workflow,
    request_summary: str,
    allow_code_changes: bool,
    context_summary: str,
) -> str:
    change_rule = (
        "You may make one bounded code change only if the workflow explicitly requires it."
        if allow_code_changes
        else "No code changes are allowed."
    )
    access_rule = {
        "debug": "Only bounded reads of files listed in the context summary are allowed. No MCP calls. No broader tool-driven repo exploration.",
        "security": "Only bounded reads of files listed in the context summary are allowed. No MCP calls. No broader tool-driven repo exploration.",
        "ship": "No shell commands. No MCP calls. No tool-driven repo exploration.",
    }[workflow]
    return f"""
WORKFLOW: {WORKFLOW_LABELS[workflow]}
REQUEST SUMMARY: {request_summary}
{change_rule}

{DOCTRINE_DIGEST}

{REPORT_BRIEFS[workflow]}

CONTEXT SUMMARY
{context_summary.strip()}

Return only JSON that matches the output schema.
{access_rule}
""".strip() + "\n"


def parse_hypothesis(final_message: str, fallback: str) -> str:
    for line in final_message.splitlines():
        if line.lower().startswith("hypothesis:"):
            value = line.split(":", 1)[1].strip()
            if value:
                return value[:120]
    return fallback[:120]


def parse_summary(final_message: str) -> str:
    for line in final_message.splitlines():
        if line.lower().startswith("summary:"):
            value = line.split(":", 1)[1].strip()
            if value:
                return value
    stripped = final_message.strip().splitlines()
    return stripped[0][:240] if stripped else ""
