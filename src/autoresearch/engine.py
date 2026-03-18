from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from .backend import resolve_codex_bin, run_codex
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
    extract_fenced_block,
    parse_hypothesis,
    parse_summary,
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
from .targets import dump_target, load_target, parse_target, resolve_target_path


RESULT_ZERO = "0.000000"


def run_validate(repo: Path, target_path: str | None, codex_bin: str | None, check_codex: bool) -> tuple[bool, list[str]]:
    messages: list[str] = []
    ok = True
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
            load_target(resolve_target_path(repo, target_path))
            messages.append(f"target ok: {target_path}")
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
    ) -> Path:
        run_id = make_run_id(f"plan-{target_name}")
        paths = make_run_paths(self.repo_root, run_id)
        prompt = build_plan_prompt(
            repo_root=self.repo_root,
            goal=goal,
            context=context,
            constraints=constraints,
            done_when=done_when,
            target_name=target_name,
        )
        iteration_dir = paths.iterations_dir / "plan"
        iteration_dir.mkdir(parents=True, exist_ok=True)
        prompt_file = iteration_dir / "prompt.md"
        final_file = iteration_dir / "codex-final.md"
        events_file = iteration_dir / "agent.jsonl"
        prompt_file.write_text(prompt, encoding="utf-8")
        result = run_codex(
            codex_bin=self.codex_bin,
            cwd=self.repo_root,
            prompt=prompt,
            final_message_file=final_file,
            agent_jsonl_file=events_file,
            model=self.model,
            profile=self.profile,
            search=self.search,
        )
        if result.exit_code != 0:
            raise BlockedRunError(result.stderr.strip() or result.stdout.strip() or "Codex plan run failed")
        yaml_block = extract_fenced_block(result.final_message, "yaml")
        if not yaml_block:
            raise ValidationError("plan output did not contain a fenced yaml block")
        target = parse_target(json.loads(json.dumps(load_yaml_string(yaml_block))))
        target.path = target_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(dump_target(target), encoding="utf-8")
        write_summary(
            paths,
            f"# Plan summary\n\n- target: `{target_path.relative_to(self.repo_root)}`\n- goal: {target.goal}\n- verify: `{target.verify.command}`\n",
        )
        engine = self._make_engine(run_id=run_id, workflow="plan", target_path=target_path, worktree_path=self.repo_root, resumable=False)
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
    ) -> RunPaths:
        run_id = make_run_id(f"{workflow}-{artifact_name}")
        paths = make_run_paths(self.repo_root, run_id)
        worktree = ensure_worktree(self.repo_root, f"autoresearch/{workflow}/{run_id}", run_id)
        engine = self._make_engine(run_id=run_id, workflow=workflow, target_path=None, worktree_path=worktree, resumable=False)
        write_engine(paths, engine)

        prompt = build_report_prompt(
            repo_root=self.repo_root,
            workflow=workflow,
            request_summary=request_summary,
            allow_code_changes=allow_code_changes,
        )
        iteration_dir = paths.iterations_dir / "1"
        iteration_dir.mkdir(parents=True, exist_ok=True)
        prompt_file = iteration_dir / "prompt.md"
        final_file = iteration_dir / "codex-final.md"
        events_file = iteration_dir / "agent.jsonl"
        prompt_file.write_text(prompt, encoding="utf-8")
        result = run_codex(
            codex_bin=self.codex_bin,
            cwd=worktree,
            prompt=prompt,
            final_message_file=final_file,
            agent_jsonl_file=events_file,
            model=self.model,
            profile=self.profile,
            search=self.search,
        )
        if result.exit_code != 0:
            raise BlockedRunError(result.stderr.strip() or result.stdout.strip() or f"Codex {workflow} run failed")
        artifact = paths.artifacts_dir / artifact_name
        artifact.write_text(result.final_message or "", encoding="utf-8")
        if extra_artifacts:
            for relative_name, content in extra_artifacts.items():
                (paths.artifacts_dir / relative_name).write_text(content, encoding="utf-8")
        summary = f"# {workflow} summary\n\n- run id: `{run_id}`\n- artifact: `{artifact.relative_to(paths.root)}`\n"
        if changed_files(worktree):
            summary += "- warning: Codex modified files during a report-only workflow; inspect the worktree before trusting the output.\n"
        write_summary(paths, summary)
        return paths

    def run_iterative_workflow(
        self,
        *,
        workflow: Workflow,
        target: TargetConfig,
        run_id: str | None = None,
        max_iterations_override: int | None = None,
        unbounded: bool = False,
        findings_text: str | None = None,
    ) -> RunPaths:
        run_id = run_id or make_run_id(f"{workflow}-{target.name}")
        paths = make_run_paths(self.repo_root, run_id)
        target.path = paths.target_file
        write_target_snapshot(paths, target)
        init_results(paths)

        engine = self._prepare_or_resume_engine(paths=paths, workflow=workflow, target=target, run_id=run_id)
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
                repo_root=self.repo_root,
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
                    verify_proc, verify_text = self._run_command(target.verify.command, Path(engine.worktree_path), context["verify_log"])
                    verify_status = f"exit:{verify_proc.returncode}"
                    if verify_proc.returncode != 0:
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
                                guard_proc, _guard_text = self._run_command(target.guard.command, Path(engine.worktree_path), context["guard_log"])
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
        return paths

    def resume_iterative_workflow(
        self,
        *,
        run_id: str | None,
        max_iterations_override: int | None,
        unbounded: bool,
        findings_text: str | None = None,
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
        engine = self._make_engine(run_id=run_id, workflow=workflow, target_path=paths.target_file, worktree_path=worktree, resumable=True)
        write_engine(paths, engine)
        return engine

    def _make_engine(self, *, run_id: str, workflow: Workflow, target_path: Path | None, worktree_path: Path, resumable: bool) -> EngineState:
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
        verify_proc, verify_text = self._run_command(target.verify.command, Path(engine.worktree_path), baseline_verify)
        if verify_proc.returncode != 0:
            raise BlockedRunError(f"baseline verify failed: {baseline_verify}")
        baseline_metric = extract_metric(target.metric.extractor, verify_text, Path(engine.worktree_path), baseline_verify)
        guard_status = "not-configured"
        if target.guard:
            guard_proc, _ = self._run_command(target.guard.command, Path(engine.worktree_path), baseline_guard)
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

    def _run_command(self, command: str, cwd: Path, log_path: Path) -> tuple[subprocess.CompletedProcess[str], str]:
        proc = subprocess.run(["/bin/zsh", "-lc", command], cwd=str(cwd), text=True, capture_output=True, check=False)
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
        ]
        if engine.warning:
            lines.append(f"- warning: {engine.warning}")
        lines.extend(["", "## Next moves"])
        if kept:
            lines.append("- Inspect the best kept experiment and decide whether to continue from this branch.")
        else:
            lines.append("- Revisit the target, verify command, or scope before continuing.")
        return "\n".join(lines)


def load_yaml_string(text: str) -> Any:
    import yaml

    return yaml.safe_load(text)


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
