from __future__ import annotations

from pathlib import Path

from .models import EngineState, TargetConfig, Workflow


RUNNER_CONTRACT = """
RUNNER CONTRACT
- The runner owns git, branching, worktrees, verification, logging, and keep/discard decisions.
- Do not run git commands.
- Do not modify .autoresearch/runs/, engine metadata, or the autoresearch runtime itself.
- Stay strictly inside the allowed scope for the task.
- Make exactly one coherent hypothesis worth of changes when a mutation is allowed.
- End your final message with these exact lines:
  Hypothesis: <one-line hypothesis>
  Summary: <short summary>
""".strip()


def build_iteration_prompt(
    *,
    repo_root: Path,
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
    agents = _read_optional(repo_root / "AGENTS.md")
    skill = _read_optional(repo_root / ".agents/skills" / f"autoresearch-{workflow}" / "SKILL.md")
    references = _read_references(repo_root, workflow)
    reflection_note = "Reflection mode is ON because the recent iterations have not improved. Re-read the target and try a meaningfully different hypothesis." if reflection_mode else ""
    findings_section = f"\nRelevant findings:\n{findings_text}\n" if findings_text else ""
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
{RUNNER_CONTRACT}

AGENTS.md
{agents}

SKILL
{skill}

REFERENCES
{references}
""".strip() + "\n"


def build_plan_prompt(
    *,
    repo_root: Path,
    goal: str,
    context: str,
    constraints: str,
    done_when: str,
    target_name: str,
) -> str:
    agents = _read_optional(repo_root / "AGENTS.md")
    skill = _read_optional(repo_root / ".agents/skills/autoresearch-plan/SKILL.md")
    references = _read_references(repo_root, "plan")
    return f"""
WORKFLOW: plan
Create a valid autoresearch target YAML for this repository.
Return exactly one fenced yaml block and no prose before it.

Target name: {target_name}
Goal: {goal}
Context: {context or '(none provided)'}
Constraints: {constraints or '(none provided)'}
Done when: {done_when or '(none provided)'}

Required schema:
- name
- goal
- scope.include
- optional scope.exclude
- metric.name
- metric.direction (higher|lower)
- metric.extractor.type (regex|jsonpath|script)
- metric.extractor.value
- verify.command
- optional guard.command
- stopping.max_iterations
- stopping.goal_threshold
- stopping.stagnation_reflect_after
- stopping.stop_after_consecutive_failures

AGENTS.md
{agents}

SKILL
{skill}

REFERENCES
{references}
""".strip() + "\n"


def build_report_prompt(
    *,
    repo_root: Path,
    workflow: Workflow,
    request_summary: str,
    allow_code_changes: bool,
) -> str:
    agents = _read_optional(repo_root / "AGENTS.md")
    skill = _read_optional(repo_root / ".agents/skills" / f"autoresearch-{workflow}" / "SKILL.md")
    references = _read_references(repo_root, workflow)
    change_rule = "No code changes are allowed in this run." if not allow_code_changes else "You may make one bounded code change only if the workflow explicitly calls for it."
    return f"""
WORKFLOW: {workflow}
REQUEST SUMMARY: {request_summary}
{change_rule}
{RUNNER_CONTRACT}

For report workflows, write the requested artifact content in the final message.

AGENTS.md
{agents}

SKILL
{skill}

REFERENCES
{references}
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


def extract_fenced_block(text: str, fence_name: str) -> str | None:
    marker = f"```{fence_name}"
    start = text.find(marker)
    if start == -1:
        return None
    start = text.find("\n", start)
    if start == -1:
        return None
    start += 1
    end = text.find("```", start)
    if end == -1:
        return None
    return text[start:end].strip() + "\n"


def _read_optional(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else f"(missing: {path})"


def _read_references(repo_root: Path, workflow: Workflow) -> str:
    references_dir = repo_root / ".agents/skills" / f"autoresearch-{workflow}" / "references"
    if not references_dir.exists():
        return "(no references)"
    chunks: list[str] = []
    for path in sorted(references_dir.glob("*.md")):
        chunks.append(f"## {path.name}\n" + path.read_text(encoding="utf-8"))
    return "\n\n".join(chunks) if chunks else "(no references)"
