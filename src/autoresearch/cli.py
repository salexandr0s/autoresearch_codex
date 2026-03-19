from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .backend import resolve_codex_bin
from .engine import Runner, load_findings_text, run_validate
from .errors import AutoresearchError
from .targets import load_target, resolve_target_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autoresearch", description="Runner-backed Codex autoresearch")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate repo assets and runtime prerequisites")
    add_common_runtime_args(validate)
    validate.add_argument("--target", help="Target file to validate")
    validate.add_argument("--skip-codex-check", action="store_true", help="Skip checking for the Codex CLI")

    plan = subparsers.add_parser("plan", help="Generate a target file with Codex")
    add_common_runtime_args(plan)
    add_codex_execution_args(plan)
    plan.add_argument("--goal", required=True)
    plan.add_argument("--context", default="")
    plan.add_argument("--constraints", default="")
    plan.add_argument("--done-when", default="")
    plan.add_argument("--target-name", default="default")
    plan.add_argument("--target-path", help="Path to write the target file")

    loop = subparsers.add_parser("loop", help="Run the experiment loop")
    add_common_runtime_args(loop)
    add_codex_execution_args(loop)
    add_iterative_args(loop)

    skill_optimize = subparsers.add_parser("skill-optimize", help="Optimize a SKILL.md with runner-backed evals")
    add_common_runtime_args(skill_optimize)
    add_codex_execution_args(skill_optimize)
    skill_optimize.add_argument("--skill", required=True, help="Path to the target SKILL.md")
    skill_optimize.add_argument("--inputs-file", required=True, help="YAML file describing test prompts")
    skill_optimize.add_argument("--evals-file", required=True, help="YAML file describing binary evals")
    skill_optimize.add_argument("--runs-per-experiment", type=int, default=3, help="How many times to run each input per verify pass")
    skill_optimize.add_argument("--references", help="Optional editable references/examples path")
    skill_optimize.add_argument("--target-name", help="Optional generated target name")
    skill_optimize.add_argument("--target-path", help="Optional generated target path")
    skill_optimize.add_argument("--max-iterations", type=int, help="Generated target max_iterations value")
    skill_optimize.add_argument("--unbounded", action="store_true", help="Ignore max_iterations and keep looping until stopped")

    debug = subparsers.add_parser("debug", help="Run a debug investigation")
    add_common_runtime_args(debug)
    add_codex_execution_args(debug)
    debug.add_argument("--summary", required=True, help="Problem statement or investigation request")

    fix = subparsers.add_parser("fix", help="Run a fix loop")
    add_common_runtime_args(fix)
    add_codex_execution_args(fix)
    add_iterative_args(fix)
    fix.add_argument("--findings-file", help="Optional findings artifact to use as context")

    security = subparsers.add_parser("security", help="Run a security review")
    add_common_runtime_args(security)
    add_codex_execution_args(security)
    security.add_argument("--summary", default="Perform a security review of the repository")
    security.add_argument("--remediate", action="store_true", help="Use the loop engine to attempt remediations")
    security.add_argument("--target", help="Target file for remediation mode")
    security.add_argument("--max-iterations", type=int)
    security.add_argument("--unbounded", action="store_true")

    ship = subparsers.add_parser("ship", help="Generate a ship checklist or dry-run plan")
    add_common_runtime_args(ship)
    add_codex_execution_args(ship)
    ship.add_argument("--summary", default="Prepare a release or deployment checklist")
    ship.add_argument("--execute", action="store_true", help="Request execute mode; the runner will refuse unattended side effects")

    resume = subparsers.add_parser("resume", help="Resume the latest or a named iterative run")
    add_common_runtime_args(resume)
    add_codex_execution_args(resume)
    resume.add_argument("--run-id", help="Run id to resume; defaults to the latest run")
    resume.add_argument("--max-iterations", type=int)
    resume.add_argument("--unbounded", action="store_true")
    resume.add_argument("--findings-file", help="Optional findings artifact to use as context")

    return parser


def add_common_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", default=".", help="Repository root to operate on")
    parser.add_argument("--codex-bin", help="Path or name of the Codex CLI binary")
    parser.add_argument("--model", help="Optional Codex model override")
    parser.add_argument("--profile", help="Optional Codex profile")
    parser.add_argument("--search", action="store_true", help="Enable Codex web search")


def add_codex_execution_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--deadline-seconds", type=int, help="Optional deadline for a Codex-backed workflow run")


def add_iterative_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--target", help="Target file to use; defaults to .autoresearch/targets/default.yaml")
    parser.add_argument("--max-iterations", type=int, help="Override stopping.max_iterations")
    parser.add_argument("--unbounded", action="store_true", help="Ignore max_iterations and keep looping until stopped")
    parser.add_argument("--run-id", help="Optional run id; if omitted, create a new run")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        repo_root = Path(args.repo).resolve()
        if args.command == "validate":
            ok, messages = run_validate(repo_root, args.target, args.codex_bin, not args.skip_codex_check)
            stream = sys.stdout if ok else sys.stderr
            for message in messages:
                print(message, file=stream)
            return 0 if ok else 1

        codex_bin = resolve_codex_bin(args.codex_bin)
        runner = Runner(repo_root=repo_root, codex_bin=codex_bin, model=args.model, profile=args.profile, search=args.search)

        if args.command == "plan":
            target_path = resolve_target_path(repo_root, args.target_path or f".autoresearch/targets/{args.target_name}.yaml")
            written = runner.run_plan(
                goal=args.goal,
                context=args.context,
                constraints=args.constraints,
                done_when=args.done_when,
                target_name=args.target_name,
                target_path=target_path,
                deadline_seconds=args.deadline_seconds,
            )
            print(str(written))
            return 0

        if args.command == "loop":
            target = load_target(resolve_target_path(repo_root, args.target))
            paths = runner.run_iterative_workflow(
                workflow="loop",
                target=target,
                run_id=args.run_id,
                max_iterations_override=args.max_iterations,
                unbounded=args.unbounded,
                deadline_seconds=args.deadline_seconds,
            )
            print(str(paths.root))
            return 0

        if args.command == "skill-optimize":
            paths = runner.run_skill_optimize(
                skill=args.skill,
                inputs_file=args.inputs_file,
                evals_file=args.evals_file,
                runs_per_experiment=args.runs_per_experiment,
                references=args.references,
                target_name=args.target_name,
                target_path=resolve_target_path(repo_root, args.target_path) if args.target_path else None,
                max_iterations=args.max_iterations,
                unbounded=args.unbounded,
                deadline_seconds=args.deadline_seconds,
            )
            print(str(paths.root))
            return 0

        if args.command == "fix":
            target = load_target(resolve_target_path(repo_root, args.target))
            findings = load_findings_text(repo_root, args.findings_file)
            paths = runner.run_iterative_workflow(
                workflow="fix",
                target=target,
                run_id=args.run_id,
                max_iterations_override=args.max_iterations,
                unbounded=args.unbounded,
                findings_text=findings,
                deadline_seconds=args.deadline_seconds,
            )
            print(str(paths.root))
            return 0

        if args.command == "debug":
            paths = runner.run_report_workflow(
                workflow="debug",
                request_summary=args.summary,
                artifact_name="findings.md",
                json_artifact_name="findings.json",
                deadline_seconds=args.deadline_seconds,
            )
            print(str(paths.root))
            return 0

        if args.command == "security":
            if args.remediate:
                target = load_target(resolve_target_path(repo_root, args.target))
                paths = runner.run_iterative_workflow(
                    workflow="security",
                    target=target,
                    max_iterations_override=args.max_iterations,
                    unbounded=args.unbounded,
                    deadline_seconds=args.deadline_seconds,
                )
            else:
                paths = runner.run_report_workflow(
                    workflow="security",
                    request_summary=args.summary,
                    artifact_name="security-report.md",
                    json_artifact_name="security-findings.json",
                    deadline_seconds=args.deadline_seconds,
                )
            print(str(paths.root))
            return 0

        if args.command == "ship":
            summary = args.summary
            if args.execute:
                summary += "\n\nExecution was requested, but the runner must not perform unattended push/publish/deploy/merge/send actions. Produce a dry-run plan only."
            paths = runner.run_report_workflow(
                workflow="ship",
                request_summary=summary,
                artifact_name="ship-checklist.md",
                extra_artifacts={"release-plan.md": summary + "\n"},
                secondary_markdown_name="release-plan.md",
                deadline_seconds=args.deadline_seconds,
            )
            print(str(paths.root))
            return 0

        if args.command == "resume":
            findings = load_findings_text(repo_root, args.findings_file)
            paths = runner.resume_iterative_workflow(
                run_id=args.run_id,
                max_iterations_override=args.max_iterations,
                unbounded=args.unbounded,
                findings_text=findings,
                deadline_seconds=args.deadline_seconds,
            )
            print(str(paths.root))
            return 0

        parser.error(f"unknown command: {args.command}")
    except AutoresearchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"unexpected error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
