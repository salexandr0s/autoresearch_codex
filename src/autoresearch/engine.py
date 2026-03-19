from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from .backend import resolve_codex_bin, run_codex
from .context import ContextPacket, build_context_workspace, build_report_fallback, infer_fallback_target
from .errors import BlockedRunError, ValidationError
from .gitops import (
    changed_files,
    commit_all,
    current_branch,
    current_short_commit,
    ensure_worktree,
    files_within_scope,
    inspect_repo,
    revert_head,
)
from .metrics import extract_metric
from .models import EngineState, ResultRow, RunPaths, TargetConfig, Workflow
from .prompts import (
    build_iteration_prompt,
    build_plan_prompt,
    build_report_prompt,
    parse_hypothesis,
    parse_summary,
)
from .platform import (
    apple_silicon_ml_status,
    collect_platform_report,
    generic_workflow_status,
    platform_warning_messages,
    render_platform_messages,
    target_platform_warning_messages,
)
from .runs import (
    append_result,
    format_recent_results,
    init_results,
    iso_now,
    latest_run_dir,
    load_engine,
    load_target_snapshot,
    make_run_id,
    make_run_paths,
    write_baseline,
    write_engine,
    write_summary,
    write_target_snapshot,
    read_results,
)
from .schemas import write_plan_output_schema, write_report_output_schema
from .skillopt import build_skill_optimize_target, load_skill_optimize_request
from .targets import dump_target, load_target, parse_target, resolve_target_path


RESULT_ZERO = "0.000000"
DEFAULT_PLAN_DEADLINE_SECONDS = 90
DEFAULT_REPORT_DEADLINE_SECONDS = 120


def run_validate(repo: Path, target_path: str | None, codex_bin: str | None, check_codex: bool) -> tuple[bool, list[str]]:
    messages: list[str] = []
    ok = True
    platform_report = collect_platform_report(codex_bin)
    messages.extend(render_platform_messages(platform_report))
    for warning in platform_warning_messages(platform_report):
        messages.append(f"warning: {warning}")

    validator = repo / "scripts" / "validate-codex-assets.py"
    if validator.exists():
        proc = subprocess.run([sys.executable, str(validator)], cwd=str(repo), text=True, capture_output=True)
        if proc.returncode != 0:
            ok = False
            messages.append(proc.stderr.strip() or proc.stdout.strip() or "asset validation failed")
        else:
            messages.append((proc.stdout or "validation passed").strip())
    else:
        ok = False
        messages.append("missing scripts/validate-codex-assets.py")

    if target_path:
        try:
            target = load_target(resolve_target_path(repo, target_path))
            messages.append(f"target ok: {target_path}")
            for warning in target_platform_warning_messages(platform_report, target):
                messages.append(f"warning: {warning}")
        except Exception as exc:  # noqa: BLE001
            ok = False
            messages.append(f"target invalid: {exc}")

    if check_codex:
        try:
            resolved = resolve_codex_bin(codex_bin)
            proc = subprocess.run([resolved, "--version"], text=True, capture_output=True, check=False)
            if proc.returncode != 0:
                raise BlockedRunError(proc.stderr.strip() or proc.stdout.strip() or "codex --version failed")
            messages.append((proc.stdout or proc.stderr).splitlines()[0].strip())
        except Exception as exc:  # noqa: BLE001
            ok = False
            messages.append(f"codex unavailable: {exc}")
    elif not platform_report.codex_available:
        messages.append("warning: Codex CLI was not verified and was not found on PATH.")

    if generic_workflow_status(platform_report) == "blocked":
        ok = False
    ml_status = apple_silicon_ml_status(platform_report)
    if platform_report.is_macos and platform_report.is_apple_silicon and ml_status == "best-effort":
        messages.append("warning: Apple Silicon ML workflows are only best-effort until the target repo confirms torch+MPS support.")
    return ok, messages


class Runner:
    def __init__(
        self,
        *,
        repo_root: Path,
        codex_bin: str,
        model: str | None = None,
        profile: str | None = None,
        search: bool = False,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.codex_bin = codex_bin
        self.model = model
        self.profile = profile
        self.search = search
        self.repo_state = inspect_repo(self.repo_root)

    def run_plan(
        self,
        *,
        goal: str,
        context: str,
        constraints: str,
        done_when: str,
        target_name: str,
        target_path: Path,
        deadline_seconds: int | None = None,
    ) -> Path:
        run_id = make_run_id(f"plan-{target_name}")
        paths = make_run_paths(self.repo_root, run_id)
        deadline_seconds = deadline_seconds or DEFAULT_PLAN_DEADLINE_SECONDS
        request_text = "\n".join(
            [
                f"goal: {goal}",
                f"context: {context or '(none provided)'}",
                f"constraints: {constraints or '(none provided)'}",
                f"done_when: {done_when or '(none provided)'}",
            ]
        )
        context_packet = build_context_workspace(
            repo_root=self.repo_root,
            workspace=paths.context_dir,
            artifacts_dir=paths.artifacts_dir,
            workflow="plan",
            request_text=request_text,
        )
        prompt = build_plan_prompt(
            target_name=target_name,
            goal=goal,
            context=context,
            constraints=constraints,
            done_when=done_when,
            context_summary=context_packet.summary_text,
        )
        iteration_dir = paths.iterations_dir / "plan"
        iteration_dir.mkdir(parents=True, exist_ok=True)
        prompt_file = iteration_dir / "prompt.md"
        final_file = iteration_dir / "codex-final.md"
        events_file = iteration_dir / "agent.jsonl"
        schema_file = write_plan_output_schema(paths.schemas_dir / "plan-output.schema.json")
        prompt_file.write_text(prompt, encoding="utf-8")
        engine = self._make_engine(
            run_id=run_id,
            workflow="plan",
            target_path=target_path,
            worktree_path=paths.context_dir,
            resumable=False,
            workspace_kind="context",
            deadline_seconds=deadline_seconds,
            prompt_bytes=len(prompt.encode("utf-8")),
            context_bytes=context_packet.total_bytes,
            selected_file_count=len(context_packet.selected_files),
        )
        write_engine(paths, engine)
        result = run_codex(
            codex_bin=self.codex_bin,
            cwd=paths.context_dir,
            prompt=prompt,
            final_message_file=final_file,
            agent_jsonl_file=events_file,
            model=self.model,
            profile=self.profile,
            search=self.search,
            deadline_seconds=deadline_seconds,
            skip_git_repo_check=True,
            output_schema_file=schema_file,
            sandbox_mode="read-only",
        )
        completion_mode = "model"
        timed_out = result.timed_out
        fallback_reason = self._codex_failure_reason(result, "Codex plan run failed")
        try:
            raw = json.loads(result.final_message)
            if not isinstance(raw, dict):
                raise ValidationError("plan output must be a JSON object")
            target = parse_target(raw)
        except Exception as exc:  # noqa: BLE001
            fallback_reason = f"{fallback_reason}; fallback used because {exc}"
            target = infer_fallback_target(
                target_name=target_name,
                goal=goal,
                constraints=constraints,
                context_packet=context_packet,
            )
            completion_mode = "fallback"
            if target is None:
                (paths.artifacts_dir / "fallback.md").write_text(
                    self._render_plan_fallback_summary(
                        target_path=target_path,
                        goal=goal,
                        context_packet=context_packet,
                        reason=fallback_reason,
                    ),
                    encoding="utf-8",
                )
                engine = replace(
                    engine,
                    status="blocked",
                    updated_at=iso_now(),
                    duration_seconds=result.duration_seconds,
                    timed_out=timed_out,
                    completion_mode="fallback",
                )
                write_engine(paths, engine)
                raise BlockedRunError(f"plan timed out or returned unusable output: {fallback_reason}")

        target.path = target_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(dump_target(target), encoding="utf-8")
        fallback_block = ""
        if completion_mode == "fallback":
            fallback_text = self._render_plan_fallback_summary(
                target_path=target_path,
                goal=goal,
                context_packet=context_packet,
                reason=fallback_reason,
            )
            (paths.artifacts_dir / "fallback.md").write_text(fallback_text, encoding="utf-8")
            fallback_block = f"- completion mode: fallback\n- fallback reason: {fallback_reason}\n"
        write_summary(
            paths,
            "# Plan summary\n\n"
            f"- target: `{target_path.relative_to(self.repo_root)}`\n"
            f"- goal: {target.goal}\n"
            f"- verify: `{target.verify.command}`\n"
            f"- deadline seconds: {deadline_seconds}\n"
            f"- duration seconds: {result.duration_seconds:.2f}\n"
            f"- prompt bytes: {len(prompt.encode('utf-8'))}\n"
            f"- context bytes: {context_packet.total_bytes}\n"
            f"- selected files: {len(context_packet.selected_files)}\n"
            f"{fallback_block}",
        )
        engine = replace(
            engine,
            status="completed",
            updated_at=iso_now(),
            duration_seconds=result.duration_seconds,
            timed_out=timed_out,
            completion_mode=completion_mode,
        )
        write_engine(paths, engine)
        return target_path

    def run_report_workflow(
        self,
        *,
        workflow: Workflow,
        request_summary: str,
        artifact_name: str,
        allow_code_changes: bool = False,
        extra_artifacts: dict[str, str] | None = None,
        deadline_seconds: int | None = None,
        json_artifact_name: str | None = None,
        secondary_markdown_name: str | None = None,
    ) -> RunPaths:
        run_id = make_run_id(f"{workflow}-{artifact_name}")
        paths = make_run_paths(self.repo_root, run_id)
        deadline_seconds = deadline_seconds or DEFAULT_REPORT_DEADLINE_SECONDS
        execution_root = ensure_worktree(self.repo_root, f"autoresearch/{workflow}/{run_id}", run_id) if allow_code_changes else paths.context_dir
        context_packet = build_context_workspace(
            repo_root=self.repo_root,
            workspace=paths.context_dir,
            artifacts_dir=paths.artifacts_dir,
            workflow=workflow,
            request_text=request_summary,
        )
        engine = self._make_engine(
            run_id=run_id,
            workflow=workflow,
            target_path=None,
            worktree_path=execution_root,
            resumable=False,
            workspace_kind="worktree" if allow_code_changes else "context",
            deadline_seconds=deadline_seconds,
            prompt_bytes=0,
            context_bytes=context_packet.total_bytes,
            selected_file_count=len(context_packet.selected_files),
        )
        write_engine(paths, engine)

        prompt = build_report_prompt(
            workflow=workflow,
            request_summary=request_summary,
            allow_code_changes=allow_code_changes,
            context_summary=context_packet.summary_text,
        )
        iteration_dir = paths.iterations_dir / "1"
        iteration_dir.mkdir(parents=True, exist_ok=True)
        prompt_file = iteration_dir / "prompt.md"
        final_file = iteration_dir / "codex-final.md"
        events_file = iteration_dir / "agent.jsonl"
        schema_file = write_report_output_schema(paths.schemas_dir / f"{workflow}-output.schema.json", workflow)
        prompt_file.write_text(prompt, encoding="utf-8")
        engine = replace(engine, prompt_bytes=len(prompt.encode("utf-8")))
        write_engine(paths, engine)
        result = run_codex(
            codex_bin=self.codex_bin,
            cwd=execution_root,
            prompt=prompt,
            final_message_file=final_file,
            agent_jsonl_file=events_file,
            model=self.model,
            profile=self.profile,
            search=self.search,
            deadline_seconds=deadline_seconds,
            skip_git_repo_check=not allow_code_changes,
            output_schema_file=schema_file,
            sandbox_mode="workspace-write" if allow_code_changes else "read-only",
        )
        fallback_reason = self._codex_failure_reason(result, f"Codex {workflow} run failed")
        completion_mode = "model"
        try:
            report_data = json.loads(result.final_message)
            self._validate_report_payload(workflow, report_data)
        except Exception as exc:  # noqa: BLE001
            completion_mode = "fallback"
            fallback_reason = f"{fallback_reason}; fallback used because {exc}"
            report_data = build_report_fallback(
                workflow=workflow,
                request_summary=request_summary,
                context_packet=context_packet,
                reason=fallback_reason,
            )
        artifact = paths.artifacts_dir / artifact_name
        artifact.write_text(self._render_report_markdown(report_data), encoding="utf-8")
        if json_artifact_name:
            (paths.artifacts_dir / json_artifact_name).write_text(json.dumps(report_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if secondary_markdown_name:
            secondary_content = report_data.get("summary", "")
            if workflow == "ship":
                secondary_parts: list[str] = []
                if extra_artifacts and secondary_markdown_name in extra_artifacts:
                    secondary_parts.append(extra_artifacts[secondary_markdown_name].rstrip())
                secondary_parts.append(str(report_data.get("release_plan_markdown", secondary_content)).rstrip())
                secondary_content = "\n\n".join(part for part in secondary_parts if part)
            elif extra_artifacts and secondary_markdown_name in extra_artifacts:
                secondary_content = extra_artifacts[secondary_markdown_name]
            (paths.artifacts_dir / secondary_markdown_name).write_text(str(secondary_content).rstrip() + "\n", encoding="utf-8")
        if extra_artifacts:
            for relative_name, content in extra_artifacts.items():
                if relative_name == secondary_markdown_name:
                    continue
                (paths.artifacts_dir / relative_name).write_text(content, encoding="utf-8")
        summary = (
            f"# {workflow} summary\n\n"
            f"- run id: `{run_id}`\n"
            f"- artifact: `{artifact.relative_to(paths.root)}`\n"
            f"- deadline seconds: {deadline_seconds}\n"
            f"- duration seconds: {result.duration_seconds:.2f}\n"
            f"- prompt bytes: {len(prompt.encode('utf-8'))}\n"
            f"- context bytes: {context_packet.total_bytes}\n"
            f"- selected files: {len(context_packet.selected_files)}\n"
            f"- completion mode: {completion_mode}\n"
        )
        if completion_mode == "fallback":
            (paths.artifacts_dir / "fallback.md").write_text(self._render_report_markdown(report_data), encoding="utf-8")
            summary += f"- fallback reason: {fallback_reason}\n"
        if allow_code_changes and changed_files(execution_root):
            summary += "- warning: Codex modified files during a report-only workflow; inspect the worktree before trusting the output.\n"
        write_summary(paths, summary)
        engine = replace(
            engine,
            status="completed",
            updated_at=iso_now(),
            duration_seconds=result.duration_seconds,
            timed_out=result.timed_out,
            completion_mode=completion_mode,
        )
        write_engine(paths, engine)
        return paths

    def run_skill_optimize(
        self,
        *,
        skill: str,
        inputs_file: str,
        evals_file: str,
        runs_per_experiment: int,
        references: str | None,
        target_name: str | None,
        target_path: Path | None,
        max_iterations: int | None,
        unbounded: bool,
        deadline_seconds: int | None = None,
    ) -> RunPaths:
        request = load_skill_optimize_request(
            repo_root=self.repo_root,
            skill=skill,
            inputs_file=inputs_file,
            evals_file=evals_file,
            runs_per_experiment=runs_per_experiment,
            target_name=target_name,
            target_path=target_path,
            references=references,
        )
        target = build_skill_optimize_target(request, max_iterations=max_iterations)
        request.target_path.parent.mkdir(parents=True, exist_ok=True)
        request.target_path.write_text(dump_target(target), encoding="utf-8")
        return self.run_iterative_workflow(
            workflow="skill-optimize",
            target=target,
            unbounded=unbounded,
            deadline_seconds=deadline_seconds,
        )

    def run_iterative_workflow(
        self,
        *,
        workflow: Workflow,
        target: TargetConfig,
        run_id: str | None = None,
        max_iterations_override: int | None = None,
        unbounded: bool = False,
        findings_text: str | None = None,
        deadline_seconds: int | None = None,
    ) -> RunPaths:
        run_id = run_id or make_run_id(f"{workflow}-{target.name}")
        paths = make_run_paths(self.repo_root, run_id)
        target.path = paths.target_file
        write_target_snapshot(paths, target)
        init_results(paths)

        engine = self._prepare_or_resume_engine(paths=paths, workflow=workflow, target=target, run_id=run_id)
        if deadline_seconds is not None and engine.deadline_seconds != deadline_seconds:
            engine = replace(engine, deadline_seconds=deadline_seconds, updated_at=iso_now())
            write_engine(paths, engine)
        best_metric, baseline_metric, failure_count = self._ensure_baseline(paths=paths, target=target, engine=engine)

        max_iterations = max_iterations_override or target.stopping.max_iterations
        rows = read_results(paths)
        start_iteration = engine.latest_iteration + 1
        stop_reason = "iteration limit reached"

        for iteration in range(start_iteration, max_iterations + 1 if not unbounded else max_iterations + 10_000_000):
            if self._goal_reached(best_metric, target):
                stop_reason = f"goal threshold reached at {best_metric:.6f}"
                break
            if failure_count >= target.stopping.stop_after_consecutive_failures:
                stop_reason = f"stopped after {failure_count} consecutive non-improving iterations"
                break

            reflection_mode = failure_count >= target.stopping.stagnation_reflect_after
            recent_results = format_recent_results(read_results(paths))
            context = self._iteration_context(paths, iteration)
            prompt = build_iteration_prompt(
                workflow=workflow,
                target=target,
                engine=engine,
                iteration=iteration,
                baseline_metric=baseline_metric,
                best_metric=best_metric,
                recent_results=recent_results,
                reflection_mode=reflection_mode,
                findings_text=findings_text,
            )
            context["prompt"].write_text(prompt, encoding="utf-8")
            result = run_codex(
                codex_bin=self.codex_bin,
                cwd=Path(engine.worktree_path),
                prompt=prompt,
                final_message_file=context["final"],
                agent_jsonl_file=context["events"],
                model=self.model,
                profile=self.profile,
                search=self.search,
                deadline_seconds=engine.deadline_seconds,
            )
            hypothesis = parse_hypothesis(result.final_message, f"{workflow} iteration {iteration}")
            files = changed_files(Path(engine.worktree_path))
            commit = current_short_commit(Path(engine.worktree_path))
            revert_commit = ""
            metric_value: float | None = None
            verify_status = "not-run"
            guard_status = "not-run"
            decision = "inconclusive"
            reason = "no_changes"

            if result.exit_code != 0 and not files:
                decision = "inconclusive"
                reason = result.stderr.strip() or result.stdout.strip() or "codex_failed"
            elif not files:
                decision = "inconclusive"
                reason = "no_changes"
            else:
                commit = commit_all(Path(engine.worktree_path), f"experiment: {hypothesis}")
                if not files_within_scope(files, target.scope):
                    decision = "discard"
                    reason = "out_of_scope_changes"
                    revert_commit = revert_head(Path(engine.worktree_path))
                else:
                    verify_proc, verify_text = self._run_command(
                        target.verify.command,
                        Path(engine.worktree_path),
                        context["verify_log"],
                        artifact_dir=context["verify_artifacts"],
                        workflow=workflow,
                    )
                    verify_status = f"exit:{verify_proc.returncode}"
                    if verify_proc.returncode != 0:
                        if "ambiguous_verify:" in verify_text:
                            decision = "inconclusive"
                            reason = "verify_ambiguous"
                        else:
                            decision = "crash"
                            reason = "verify_failed"
                        revert_commit = revert_head(Path(engine.worktree_path))
                    else:
                        try:
                            metric_value = extract_metric(target.metric.extractor, verify_text, Path(engine.worktree_path), context["verify_log"])
                        except ValidationError as exc:
                            decision = "inconclusive"
                            reason = f"metric_parse_failed: {exc}"
                            revert_commit = revert_head(Path(engine.worktree_path))
                        else:
                            if target.guard:
                                guard_proc, _guard_text = self._run_command(
                                    target.guard.command,
                                    Path(engine.worktree_path),
                                    context["guard_log"],
                                    artifact_dir=context["verify_artifacts"],
                                    workflow=workflow,
                                )
                                guard_status = f"exit:{guard_proc.returncode}"
                                if guard_proc.returncode != 0:
                                    decision = "discard"
                                    reason = "guard_failed"
                                    revert_commit = revert_head(Path(engine.worktree_path))
                                else:
                                    decision, reason, revert_commit, best_metric = self._accept_or_reject(
                                        metric_value=metric_value,
                                        best_metric=best_metric,
                                        target=target,
                                        worktree=Path(engine.worktree_path),
                                    )
                            else:
                                guard_status = "not-configured"
                                decision, reason, revert_commit, best_metric = self._accept_or_reject(
                                    metric_value=metric_value,
                                    best_metric=best_metric,
                                    target=target,
                                    worktree=Path(engine.worktree_path),
                                )

            if decision == "keep":
                failure_count = 0
            else:
                failure_count += 1

            metric_string = f"{metric_value:.6f}" if metric_value is not None else RESULT_ZERO if decision == "crash" else ""
            best_string = f"{best_metric:.6f}"
            delta_string = f"{(metric_value - best_metric):.6f}" if metric_value is not None else ""
            row = ResultRow(
                iteration=iteration,
                timestamp=iso_now(),
                branch=current_branch(Path(engine.worktree_path)),
                commit=commit,
                revert_commit=revert_commit,
                metric=metric_string,
                best_metric=best_string,
                delta_from_best=delta_string,
                verify_status=verify_status,
                guard_status=guard_status,
                decision=decision,
                hypothesis=hypothesis,
                files_touched=",".join(files),
                artifact_path=str(context["dir"].relative_to(paths.root)),
                decision_reason=reason,
            )
            append_result(paths, row)
            engine = replace(engine, latest_iteration=iteration, best_metric=best_metric, best_iteration=iteration if decision == "keep" else engine.best_iteration, updated_at=iso_now(), status="running")
            write_engine(paths, engine)
            rows = read_results(paths)
        else:
            stop_reason = "iteration limit reached" if not unbounded else "unbounded loop interrupted by external stop"

        engine = replace(engine, status="completed", updated_at=iso_now(), best_metric=best_metric, baseline_metric=baseline_metric)
        write_engine(paths, engine)
        write_summary(paths, self._build_summary(target=target, rows=rows, baseline_metric=baseline_metric, best_metric=best_metric, stop_reason=stop_reason, engine=engine))
        if workflow == "skill-optimize":
            self._write_skill_optimize_artifacts(
                paths=paths,
                target=target,
                rows=rows,
                baseline_metric=baseline_metric,
                best_metric=best_metric,
                stop_reason=stop_reason,
            )
        return paths

    def resume_iterative_workflow(
        self,
        *,
        run_id: str | None,
        max_iterations_override: int | None,
        unbounded: bool,
        findings_text: str | None = None,
        deadline_seconds: int | None = None,
    ) -> RunPaths:
        run_dir = self._resolve_run_dir(run_id)
        engine = load_engine(run_dir)
        if not engine.resumable:
            raise BlockedRunError(f"workflow {engine.workflow} is not resumable")
        paths = make_run_paths(self.repo_root, engine.run_id)
        target = load_target_snapshot(paths)
        return self.run_iterative_workflow(
            workflow=engine.workflow,
            target=target,
            run_id=engine.run_id,
            max_iterations_override=max_iterations_override,
            unbounded=unbounded,
            findings_text=findings_text,
            deadline_seconds=deadline_seconds,
        )

    def _prepare_or_resume_engine(self, *, paths: RunPaths, workflow: Workflow, target: TargetConfig, run_id: str) -> EngineState:
        if paths.engine_file.exists():
            existing = load_engine(paths.root)
            worktree = ensure_worktree(self.repo_root, existing.run_branch, run_id, existing.worktree_path)
            updated = replace(existing, worktree_path=str(worktree), updated_at=iso_now(), target_path=str(paths.target_file))
            write_engine(paths, updated)
            return updated
        run_branch = f"autoresearch/{workflow}/{run_id}"
        worktree = ensure_worktree(self.repo_root, run_branch, run_id)
        engine = self._make_engine(
            run_id=run_id,
            workflow=workflow,
            target_path=paths.target_file,
            worktree_path=worktree,
            resumable=True,
        )
        write_engine(paths, engine)
        return engine

    def _make_engine(
        self,
        *,
        run_id: str,
        workflow: Workflow,
        target_path: Path | None,
        worktree_path: Path,
        resumable: bool,
        workspace_kind: str = "worktree",
        deadline_seconds: int | None = None,
        prompt_bytes: int = 0,
        context_bytes: int = 0,
        selected_file_count: int = 0,
    ) -> EngineState:
        warning = None
        if self.repo_state.dirty:
            warning = "source repository was dirty at run start; experiments use a dedicated worktree from HEAD and ignore uncommitted changes"
        return EngineState(
            run_id=run_id,
            workflow=workflow,
            target_repo=str(self.repo_root),
            source_branch=self.repo_state.branch,
            source_head=self.repo_state.head,
            run_branch=f"autoresearch/{workflow}/{run_id}",
            worktree_path=str(worktree_path),
            codex_bin=self.codex_bin,
            model=self.model,
            profile=self.profile,
            search=self.search,
            target_path=str(target_path) if target_path else None,
            status="initialized",
            created_at=iso_now(),
            updated_at=iso_now(),
            resumable=resumable,
            warning=warning,
            workspace_kind=workspace_kind,
            deadline_seconds=deadline_seconds,
            prompt_bytes=prompt_bytes,
            context_bytes=context_bytes,
            selected_file_count=selected_file_count,
        )

    def _ensure_baseline(self, *, paths: RunPaths, target: TargetConfig, engine: EngineState) -> tuple[float, float, int]:
        rows = read_results(paths)
        if rows:
            baseline_metric = float(rows[0]["metric"])
            best_metric = float(rows[-1]["best_metric"] or rows[0]["metric"])
            failures = 0
            for row in reversed(rows[1:]):
                if row["decision"] == "keep":
                    break
                failures += 1
            return best_metric, baseline_metric, failures

        baseline_verify = paths.artifacts_dir / "baseline-verify.log"
        baseline_guard = paths.artifacts_dir / "baseline-guard.log"
        verify_proc, verify_text = self._run_command(
            target.verify.command,
            Path(engine.worktree_path),
            baseline_verify,
            artifact_dir=paths.artifacts_dir / "baseline",
            workflow=engine.workflow,
        )
        if verify_proc.returncode != 0:
            raise BlockedRunError(f"baseline verify failed: {baseline_verify}")
        baseline_metric = extract_metric(target.metric.extractor, verify_text, Path(engine.worktree_path), baseline_verify)
        guard_status = "not-configured"
        if target.guard:
            guard_proc, _ = self._run_command(
                target.guard.command,
                Path(engine.worktree_path),
                baseline_guard,
                artifact_dir=paths.artifacts_dir / "baseline",
                workflow=engine.workflow,
            )
            if guard_proc.returncode != 0:
                raise BlockedRunError(f"baseline guard failed: {baseline_guard}")
            guard_status = f"exit:{guard_proc.returncode}"
        write_baseline(
            paths,
            {
                "run_id": engine.run_id,
                "timestamp": iso_now(),
                "repo_root": str(self.repo_root),
                "git_repository": True,
                "branch": self.repo_state.branch,
                "head": self.repo_state.head,
                "dirty": self.repo_state.dirty,
                "isolation_mode": "worktree",
                "verify_command": target.verify.command,
                "guard_command": target.guard.command if target.guard else None,
                "parsed_baseline_metric": baseline_metric,
                "parse_status": "ok",
            },
        )
        row = ResultRow(
            iteration=0,
            timestamp=iso_now(),
            branch=current_branch(Path(engine.worktree_path)),
            commit=current_short_commit(Path(engine.worktree_path)),
            revert_commit="",
            metric=f"{baseline_metric:.6f}",
            best_metric=f"{baseline_metric:.6f}",
            delta_from_best="0.000000",
            verify_status=f"exit:{verify_proc.returncode}",
            guard_status=guard_status,
            decision="baseline",
            hypothesis="baseline",
            files_touched="",
            artifact_path=str(paths.artifacts_dir.relative_to(paths.root)),
            decision_reason="baseline",
        )
        append_result(paths, row)
        updated = replace(engine, baseline_metric=baseline_metric, best_metric=baseline_metric, best_iteration=0, updated_at=iso_now(), status="running")
        write_engine(paths, updated)
        return baseline_metric, baseline_metric, 0

    def _run_command(
        self,
        command: str,
        cwd: Path,
        log_path: Path,
        *,
        artifact_dir: Path | None = None,
        workflow: Workflow | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        env = os.environ.copy()
        env["AUTORESEARCH_CODEX_BIN"] = self.codex_bin
        env["AUTORESEARCH_PYTHON_BIN"] = sys.executable
        env["AUTORESEARCH_MODEL"] = self.model or ""
        env["AUTORESEARCH_PROFILE"] = self.profile or ""
        env["AUTORESEARCH_SEARCH"] = "1" if self.search else "0"
        env["AUTORESEARCH_TARGET_REPO"] = str(self.repo_root)
        if workflow:
            env["AUTORESEARCH_WORKFLOW"] = workflow
        if artifact_dir is not None:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            env["AUTORESEARCH_VERIFY_ARTIFACT_DIR"] = str(artifact_dir)
        proc = subprocess.run(["/bin/zsh", "-lc", command], cwd=str(cwd), text=True, capture_output=True, check=False, env=env)
        combined = (proc.stdout or "") + (proc.stderr or "")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(combined, encoding="utf-8")
        return proc, combined

    def _accept_or_reject(self, *, metric_value: float, best_metric: float, target: TargetConfig, worktree: Path) -> tuple[str, str, str, float]:
        if self._is_improvement(metric_value, best_metric, target):
            return "keep", "metric_improved", "", metric_value
        revert_commit = revert_head(worktree)
        return "discard", "metric_not_improved", revert_commit, best_metric

    def _goal_reached(self, metric_value: float, target: TargetConfig) -> bool:
        threshold = target.stopping.goal_threshold
        if threshold is None:
            return False
        if target.metric.direction == "higher":
            return metric_value >= threshold
        return metric_value <= threshold

    def _is_improvement(self, metric_value: float, best_metric: float, target: TargetConfig) -> bool:
        if target.metric.direction == "higher":
            return metric_value > best_metric
        return metric_value < best_metric

    def _iteration_context(self, paths: RunPaths, iteration: int) -> dict[str, Path]:
        directory = paths.iterations_dir / str(iteration)
        directory.mkdir(parents=True, exist_ok=True)
        return {
            "dir": directory,
            "prompt": directory / "prompt.md",
            "final": directory / "codex-final.md",
            "verify_log": directory / "verify.log",
            "verify_artifacts": directory / "verify-artifacts",
            "guard_log": directory / "guard.log",
            "events": directory / "agent.jsonl",
        }

    def _resolve_run_dir(self, run_id: str | None) -> Path:
        if run_id:
            path = self.repo_root / ".autoresearch" / "runs" / run_id
            if not path.exists():
                raise BlockedRunError(f"run not found: {run_id}")
            return path
        latest = latest_run_dir(self.repo_root)
        if latest is None:
            raise BlockedRunError("no runs found to resume")
        return latest

    def _build_summary(
        self,
        *,
        target: TargetConfig,
        rows: list[dict[str, str]],
        baseline_metric: float,
        best_metric: float,
        stop_reason: str,
        engine: EngineState,
    ) -> str:
        kept = [row for row in rows if row.get("decision") == "keep"]
        discarded = [row for row in rows if row.get("decision") in {"discard", "crash", "inconclusive", "blocked"}]
        guard_green = all(row.get("guard_status") not in {"exit:1", "exit:2"} for row in rows if row.get("guard_status"))
        lines = [
            f"# {engine.workflow} summary",
            "",
            f"- goal: {target.goal}",
            f"- baseline metric: {baseline_metric:.6f}",
            f"- best metric: {best_metric:.6f}",
            f"- kept experiments: {len(kept)}",
            f"- discarded experiments: {len(discarded)}",
            f"- guard stayed green: {'yes' if guard_green else 'no'}",
            f"- stop reason: {stop_reason}",
            f"- workspace kind: {engine.workspace_kind}",
        ]
        if engine.deadline_seconds is not None:
            lines.append(f"- deadline seconds: {engine.deadline_seconds}")
        if engine.duration_seconds is not None:
            lines.append(f"- duration seconds: {engine.duration_seconds:.2f}")
        if engine.prompt_bytes:
            lines.append(f"- prompt bytes: {engine.prompt_bytes}")
        if engine.context_bytes:
            lines.append(f"- context bytes: {engine.context_bytes}")
        if engine.selected_file_count:
            lines.append(f"- selected files: {engine.selected_file_count}")
        if engine.completion_mode != "model":
            lines.append(f"- completion mode: {engine.completion_mode}")
        if engine.warning:
            lines.append(f"- warning: {engine.warning}")
        lines.extend(["", "## Next moves"])
        if kept:
            lines.append("- Inspect the best kept experiment and decide whether to continue from this branch.")
        else:
            lines.append("- Revisit the target, verify command, or scope before continuing.")
        return "\n".join(lines)

    def _write_skill_optimize_artifacts(
        self,
        *,
        paths: RunPaths,
        target: TargetConfig,
        rows: list[dict[str, str]],
        baseline_metric: float,
        best_metric: float,
        stop_reason: str,
    ) -> None:
        changelog_lines = [
            "# skill-optimize changelog",
            "",
            f"- target: {target.name}",
            f"- metric: {target.metric.name}",
            f"- baseline metric: {baseline_metric:.6f}",
            f"- best metric: {best_metric:.6f}",
            "",
            "## Iterations",
        ]
        for row in rows:
            iteration = row.get("iteration", "")
            decision = row.get("decision", "")
            hypothesis = row.get("hypothesis", "")
            reason = row.get("decision_reason", "")
            metric = row.get("metric", "")
            if iteration == "0":
                changelog_lines.append(f"- baseline: metric {metric}")
                continue
            changelog_lines.append(f"- iteration {iteration}: {decision} | metric {metric or '(n/a)'} | {hypothesis} | {reason}")
        (paths.artifacts_dir / "changelog.md").write_text("\n".join(changelog_lines).rstrip() + "\n", encoding="utf-8")

        summary_payload = {
            "target": target.name,
            "metric": target.metric.name,
            "baseline_metric": baseline_metric,
            "best_metric": best_metric,
            "stop_reason": stop_reason,
            "rows": rows,
        }
        (paths.artifacts_dir / "score-summary.json").write_text(
            json.dumps(summary_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _codex_failure_reason(self, result: Any, default: str) -> str:
        details = result.stderr.strip() or result.stdout.strip() or default
        if result.timed_out:
            return f"deadline exceeded after {result.duration_seconds:.2f}s"
        return details

    def _render_plan_fallback_summary(
        self,
        *,
        target_path: Path,
        goal: str,
        context_packet: ContextPacket,
        reason: str,
    ) -> str:
        return (
            "# Plan fallback\n\n"
            f"- target: `{target_path.relative_to(self.repo_root)}`\n"
            f"- goal: {goal}\n"
            f"- reason: {reason}\n"
            f"- candidate verify commands: {', '.join(context_packet.candidate_verify_commands) or '(none)'}\n"
            f"- candidate scopes: {', '.join(context_packet.candidate_scope_globs) or '(none)'}\n"
            f"- candidate metrics: {', '.join(item['name'] for item in context_packet.metric_candidates) or '(none)'}\n"
        )

    def _render_report_markdown(self, report_data: dict[str, Any]) -> str:
        if "checklist_markdown" in report_data:
            markdown = str(report_data.get("checklist_markdown", "")).rstrip()
            return markdown + "\n" if markdown else "# Ship report\n\n"
        markdown = str(report_data.get("artifact_markdown", "")).rstrip()
        if markdown:
            return markdown + "\n"
        lines = [f"# {report_data.get('title', 'Report')}", "", report_data.get("summary", "")]
        return "\n".join(lines).rstrip() + "\n"

    def _validate_report_payload(self, workflow: Workflow, payload: Any) -> None:
        if not isinstance(payload, dict):
            raise ValidationError("report output must be a JSON object")
        if workflow == "ship":
            required = ["title", "summary", "checklist_markdown", "release_plan_markdown"]
        else:
            required = ["title", "summary", "findings", "artifact_markdown"]
        missing = [key for key in required if key not in payload]
        if missing:
            raise ValidationError(f"report output missing required keys: {', '.join(missing)}")


def load_findings_text(repo_root: Path, explicit_path: str | None = None) -> str | None:
    if explicit_path:
        path = Path(explicit_path)
        if not path.is_absolute():
            path = repo_root / path
        if path.exists():
            return path.read_text(encoding="utf-8")
    runs_root = repo_root / ".autoresearch" / "runs"
    if not runs_root.exists():
        return None
    candidates = sorted(runs_root.glob("*/artifacts/findings.md"))
    if not candidates:
        return None
    return candidates[-1].read_text(encoding="utf-8")


def scaffold_copy(src_repo: Path, dest_repo: Path) -> None:
    for relative in ["AGENTS.md", ".agents", ".autoresearch/targets/default.yaml", ".codex/config.toml", "codex/rules/safety.rules"]:
        src = src_repo / relative
        dest = dest_repo / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)
