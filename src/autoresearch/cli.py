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
    plan.add_argument("--goal", required=True)
    plan.add_argument("--context", default="")
    plan.add_argument("--constraints", default="")
    plan.add_argument("--done-when", default="")
    plan.add_argument("--target-name", default="default")
    plan.add_argument("--target-path", help="Path to write the target file")

    loop = subparsers.add_parser("loop", help="Run the experiment loop")
    add_common_runtime_args(loop)
    add_iterative_args(loop)

    debug = subparsers.add_parser("debug", help="Run a debug investigation")
    add_common_runtime_args(debug)
    debug.add_argument("--summary", required=True, help="Problem statement or investigation request")

    fix = subparsers.add_parser("fix", help="Run a fix loop")
    add_common_runtime_args(fix)
    add_iterative_args(fix)
    fix.add_argument("--findings-file", help="Optional findings artifact to use as context")

    security = subparsers.add_parser("security", help="Run a security review")
    add_common_runtime_args(security)
    security.add_argument("--summary", default="Perform a security review of the repository")
    security.add_argument("--remediate", action="store_true", help="Use the loop engine to attempt remediations")
    security.add_argument("--target", help="Target file for remediation mode")
    security.add_argument("--max-iterations", type=int)
    security.add_argument("--unbounded", action="store_true")

    ship = subparsers.add_parser("ship", help="Generate a ship checklist or dry-run plan")
    add_common_runtime_args(ship)
    ship.add_argument("--summary", default="Prepare a release or deployment checklist")
    ship.add_argument("--execute", action="store_true", help="Request execute mode; the runner will refuse unattended side effects")

    resume = subparsers.add_parser("resume", help="Resume the latest or a named iterative run")
    add_common_runtime_args(resume)
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
            )
            print(str(paths.root))
            return 0

        if args.command == "debug":
            paths = runner.run_report_workflow(
                workflow="debug",
                request_summary=args.summary,
                artifact_name="findings.md",
                extra_artifacts={"findings.json": json.dumps({"summary": args.summary}, indent=2) + "\n"},
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
                )
            else:
                paths = runner.run_report_workflow(
                    workflow="security",
                    request_summary=args.summary,
                    artifact_name="security-report.md",
                    extra_artifacts={"security-findings.json": json.dumps({"summary": args.summary}, indent=2) + "\n"},
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
