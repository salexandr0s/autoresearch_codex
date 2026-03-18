from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .models import CommandConfig, MetricConfig, MetricExtractor, ScopeConfig, StoppingConfig, TargetConfig, Workflow

TEXT_SUFFIXES = {".md", ".toml", ".yaml", ".yml", ".json", ".py", ".sh", ".txt"}
MAX_FILE_BYTES = 4_000
MAX_FILE_LINES = 220
MAX_CONTEXT_BYTES = 40_000
MAX_FILES_BY_WORKFLOW = {
    "plan": 6,
    "debug": 6,
    "security": 6,
    "ship": 6,
}
SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
    "test-fixtures",
}
STOPWORDS = {
    "the",
    "and",
    "with",
    "that",
    "this",
    "from",
    "into",
    "only",
    "stay",
    "need",
    "repo",
    "repository",
    "workflow",
    "runtime",
    "new",
    "after",
    "when",
    "what",
    "your",
    "will",
    "must",
    "should",
}


@dataclass(slots=True)
class ContextFile:
    source_path: str
    context_path: str
    original_bytes: int
    copied_bytes: int
    excerpted: bool
    score: int


@dataclass(slots=True)
class ContextPacket:
    workflow: Workflow
    workspace: Path
    manifest_path: Path
    summary_path: Path
    summary_text: str
    selected_files: list[ContextFile]
    total_bytes: int
    candidate_verify_commands: list[str]
    candidate_scope_globs: list[str]
    metric_candidates: list[dict[str, Any]]
    repo_facts: dict[str, Any]

    def manifest(self) -> dict[str, Any]:
        return {
            "workflow": self.workflow,
            "workspace": str(self.workspace),
            "summary_path": str(self.summary_path.name),
            "selected_files": [asdict(item) for item in self.selected_files],
            "total_bytes": self.total_bytes,
            "candidate_verify_commands": self.candidate_verify_commands,
            "candidate_scope_globs": self.candidate_scope_globs,
            "metric_candidates": self.metric_candidates,
            "repo_facts": self.repo_facts,
        }


def build_context_workspace(
    *,
    repo_root: Path,
    workspace: Path,
    artifacts_dir: Path,
    workflow: Workflow,
    request_text: str,
) -> ContextPacket:
    workspace.mkdir(parents=True, exist_ok=True)
    files_dir = workspace / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    repo_facts = _gather_repo_facts(repo_root)
    candidate_verify_commands = _guess_verify_commands(repo_root, repo_facts)
    candidate_scope_globs = _guess_scope_globs(repo_root, workflow, request_text)
    metric_candidates = _guess_metric_candidates(repo_facts, request_text)
    selected = _select_context_files(repo_root, workflow, request_text, repo_facts)

    context_files: list[ContextFile] = []
    total_bytes = 0
    for source_rel, score in selected:
        source_path = repo_root / source_rel
        copied_text, excerpted = _read_excerpt(source_path)
        if total_bytes + len(copied_text.encode("utf-8")) > MAX_CONTEXT_BYTES:
            continue
        dest_path = files_dir / source_rel
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(copied_text, encoding="utf-8")
        copied_bytes = len(copied_text.encode("utf-8"))
        total_bytes += copied_bytes
        context_files.append(
            ContextFile(
                source_path=source_rel,
                context_path=str(dest_path.relative_to(workspace)),
                original_bytes=source_path.stat().st_size,
                copied_bytes=copied_bytes,
                excerpted=excerpted,
                score=score,
            )
        )

    summary_text = _render_context_summary(
        workflow=workflow,
        request_text=request_text,
        repo_facts=repo_facts,
        candidate_verify_commands=candidate_verify_commands,
        candidate_scope_globs=candidate_scope_globs,
        metric_candidates=metric_candidates,
        selected_files=context_files,
    )

    summary_path = workspace / "summary.md"
    manifest_path = workspace / "manifest.json"
    summary_path.write_text(summary_text, encoding="utf-8")
    manifest_path.write_text(json.dumps(
        {
            "workflow": workflow,
            "repo_facts": repo_facts,
            "candidate_verify_commands": candidate_verify_commands,
            "candidate_scope_globs": candidate_scope_globs,
            "metric_candidates": metric_candidates,
            "selected_files": [asdict(item) for item in context_files],
        },
        indent=2,
        sort_keys=True,
    ) + "\n", encoding="utf-8")

    (artifacts_dir / "context-summary.md").write_text(summary_text, encoding="utf-8")
    (artifacts_dir / "context-manifest.json").write_text(json.dumps(
        {
            "workflow": workflow,
            "repo_facts": repo_facts,
            "candidate_verify_commands": candidate_verify_commands,
            "candidate_scope_globs": candidate_scope_globs,
            "metric_candidates": metric_candidates,
            "selected_files": [asdict(item) for item in context_files],
            "total_bytes": total_bytes,
        },
        indent=2,
        sort_keys=True,
    ) + "\n", encoding="utf-8")

    return ContextPacket(
        workflow=workflow,
        workspace=workspace,
        manifest_path=manifest_path,
        summary_path=summary_path,
        summary_text=summary_text,
        selected_files=context_files,
        total_bytes=total_bytes,
        candidate_verify_commands=candidate_verify_commands,
        candidate_scope_globs=candidate_scope_globs,
        metric_candidates=metric_candidates,
        repo_facts=repo_facts,
    )


def infer_fallback_target(
    *,
    target_name: str,
    goal: str,
    constraints: str,
    context_packet: ContextPacket,
) -> TargetConfig | None:
    verify_command = next(iter(context_packet.candidate_verify_commands), None)
    scope_globs = _explicit_scope_globs(constraints) or context_packet.candidate_scope_globs
    metric = _choose_metric_candidate(goal, context_packet.metric_candidates)
    if not verify_command or not scope_globs or not metric:
        return None
    return TargetConfig(
        name=target_name,
        goal=goal,
        scope=ScopeConfig(include=scope_globs, exclude=[]),
        metric=MetricConfig(
            metric["name"],
            metric["direction"],
            MetricExtractor(metric["extractor"]["type"], metric["extractor"]["value"]),
        ),
        verify=CommandConfig(verify_command),
        guard=None,
        stopping=StoppingConfig(
            max_iterations=10,
            goal_threshold=metric.get("goal_threshold"),
            stagnation_reflect_after=5,
            stop_after_consecutive_failures=10,
        ),
    )


def build_report_fallback(
    *,
    workflow: Workflow,
    request_summary: str,
    context_packet: ContextPacket,
    reason: str,
) -> dict[str, Any]:
    selected = "\n".join(f"- `{item.source_path}`" for item in context_packet.selected_files) or "- none"
    artifact_markdown = "\n\n".join(
        [
            "## Why this is a fallback\n\n"
            f"The live Codex run did not complete normally. Reason: {reason}. This fallback was generated by the runner from bounded repository context.",
            f"## Repository context\n\n{context_packet.summary_text.strip()}",
            f"## Selected files\n\n{selected}",
            f"## Recommended next steps\n\n{_fallback_next_steps(workflow, context_packet)}",
        ]
    )
    if workflow == "ship":
        return {
            "title": "Ship fallback report",
            "summary": "Structured fallback generated because the live ship run exceeded its deadline or returned unusable output.",
            "checklist_markdown": artifact_markdown + "\n",
            "release_plan_markdown": _fallback_next_steps(workflow, context_packet) + "\n",
        }
    return {
        "title": f"{workflow.title()} fallback report",
        "summary": f"Structured fallback generated because the live {workflow} run exceeded its deadline or returned unusable output.",
        "findings": [],
        "artifact_markdown": artifact_markdown + "\n",
    }


def _gather_repo_facts(repo_root: Path) -> dict[str, Any]:
    manifests = [name for name in ["pyproject.toml", "package.json", "Cargo.toml", "go.mod", "README.md", "uv.lock"] if (repo_root / name).exists()]
    top_level = sorted(path.name for path in repo_root.iterdir() if not path.name.startswith("."))
    tests_dir = repo_root / "tests"
    src_dir = repo_root / "src"
    docs_dir = repo_root / "docs"
    test_files = sum(1 for _ in _iter_text_files(tests_dir)) if tests_dir.exists() else 0
    src_files = sum(1 for _ in _iter_text_files(src_dir)) if src_dir.exists() else 0
    has_unittest = _tests_use_unittest(repo_root)
    has_pytest = _tests_use_pytest(repo_root)
    return {
        "repo_name": repo_root.name,
        "manifests": manifests,
        "top_level_entries": top_level[:20],
        "has_tests_dir": tests_dir.exists(),
        "has_src_dir": src_dir.exists(),
        "has_docs_dir": docs_dir.exists(),
        "test_file_count": test_files,
        "src_file_count": src_files,
        "has_unittest": has_unittest,
        "has_pytest": has_pytest,
        "existing_targets": sorted(path.name for path in (repo_root / ".autoresearch" / "targets").glob("*.yaml")) if (repo_root / ".autoresearch" / "targets").exists() else [],
    }


def _guess_verify_commands(repo_root: Path, repo_facts: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    if repo_facts.get("has_tests_dir") and repo_facts.get("has_unittest"):
        if (repo_root / "uv.lock").exists():
            commands.append("uv run python -m unittest discover -s tests -v")
        if repo_facts.get("has_src_dir"):
            commands.append("PYTHONPATH=src python3 -m unittest discover -s tests -v")
        commands.append("python3 -m unittest discover -s tests -v")
    if repo_facts.get("has_tests_dir") and repo_facts.get("has_pytest"):
        if (repo_root / "uv.lock").exists():
            commands.append("uv run pytest -q")
        commands.append("pytest -q")
    unique: list[str] = []
    for item in commands:
        if item not in unique:
            unique.append(item)
    return unique


def _guess_scope_globs(repo_root: Path, workflow: Workflow, request_text: str) -> list[str]:
    explicit = _explicit_scope_globs(request_text)
    if explicit:
        return explicit
    lowered = request_text.lower()
    scopes: list[str] = []
    if "test" in lowered or "coverage" in lowered or "regression" in lowered:
        if (repo_root / "tests").exists():
            scopes.append("tests/**")
    if (repo_root / "src").exists():
        if workflow in {"debug", "security"} or "src" in lowered or "fix" in lowered or "runtime" in lowered:
            scopes.append("src/**")
    if not scopes and (repo_root / "src").exists():
        scopes.append("src/**")
    if not scopes and (repo_root / "tests").exists():
        scopes.append("tests/**")
    return scopes[:4]


def _guess_metric_candidates(repo_facts: dict[str, Any], request_text: str) -> list[dict[str, Any]]:
    lowered = request_text.lower()
    candidates: list[dict[str, Any]] = []
    if repo_facts.get("has_tests_dir") and repo_facts.get("has_unittest"):
        candidates.append(
            {
                "name": "test_count",
                "direction": "higher",
                "goal_threshold": None,
                "when": "Use when the goal is broader regression coverage or more passing tests.",
                "extractor": {"type": "regex", "value": r"Ran ([0-9]+) tests?"},
            }
        )
    if "fail" in lowered or "error" in lowered or "fix" in lowered or "debug" in lowered:
        candidates.insert(
            0,
            {
                "name": "test_count",
                "direction": "higher",
                "goal_threshold": None,
                "when": "Fallback candidate when only passing-test count can be inferred mechanically.",
                "extractor": {"type": "regex", "value": r"Ran ([0-9]+) tests?"},
            }
        )
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        key = (candidate["name"], candidate["direction"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _select_context_files(repo_root: Path, workflow: Workflow, request_text: str, repo_facts: dict[str, Any]) -> list[tuple[str, int]]:
    limit = MAX_FILES_BY_WORKFLOW.get(workflow, 12)
    pinned = _pinned_files(repo_root, workflow)
    selected: list[tuple[str, int]] = []
    seen: set[str] = set()
    for item in pinned:
        if item.exists() and item.is_file():
            rel = item.relative_to(repo_root).as_posix()
            selected.append((rel, 100))
            seen.add(rel)

    query_terms = _query_terms(request_text, workflow)
    scored: list[tuple[int, str]] = []
    for path in _iter_text_files(repo_root):
        rel = path.relative_to(repo_root).as_posix()
        if rel in seen:
            continue
        if not _is_context_candidate(rel, workflow):
            continue
        score = _score_file(path, query_terms, workflow, repo_facts)
        if score <= 0:
            continue
        scored.append((score, rel))

    for score, rel in sorted(scored, key=lambda item: (-item[0], item[1])):
        if len(selected) >= limit:
            break
        selected.append((rel, score))
        seen.add(rel)
    return selected[:limit]


def _pinned_files(repo_root: Path, workflow: Workflow) -> list[Path]:
    pinned: list[Path] = []
    shared = ["README.md", "pyproject.toml", "package.json"]
    if workflow == "plan":
        shared.append(".autoresearch/targets/default.yaml")
    for relative in shared:
        path = repo_root / relative
        if path.exists():
            pinned.append(path)
    if workflow == "ship":
        for relative in ["scripts/release.sh", "docs/maintainers/release.md", "docs/maintainers/smoke.md", "docs/workflows/ship.md"]:
            path = repo_root / relative
            if path.exists():
                pinned.append(path)
    if workflow == "security":
        for relative in ["AGENTS.md", ".codex/config.toml"]:
            path = repo_root / relative
            if path.exists():
                pinned.append(path)
    return pinned


def _query_terms(text: str, workflow: Workflow) -> list[str]:
    terms = {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", text.lower())
        if token not in STOPWORDS
    }
    terms.update(
        {
            "metric",
            "verify",
            "scope",
            workflow,
        }
    )
    if workflow == "plan":
        terms.update({"target", "tests", "src"})
    elif workflow == "debug":
        terms.update({"debug", "fail", "error", "traceback"})
    elif workflow == "security":
        terms.update({"security", "secret", "subprocess", "token", "auth"})
    elif workflow == "ship":
        terms.update({"release", "deploy", "ship", "checklist", "smoke"})
    return sorted(terms)


def _score_file(path: Path, query_terms: list[str], workflow: Workflow, repo_facts: dict[str, Any]) -> int:
    rel = path.as_posix()
    score = 0
    if workflow == "plan" and any(name in rel for name in ["pyproject.toml", "README.md", "tests/", "src/"]):
        score += 5
    if workflow == "debug" and any(name in rel for name in ["src/", "tests/"]):
        score += 4
    if workflow == "security" and any(name in rel for name in ["src/", "scripts/", ".codex/", "AGENTS.md"]):
        score += 4
    if workflow == "ship" and any(name in rel for name in ["README.md", "docs/", "scripts/", "pyproject.toml"]):
        score += 4
    if workflow == "ship" and any(name in rel for name in ["test-fixtures/", ".agents/skills/", ".autoresearch/targets/"]):
        score -= 6
    if workflow in {"plan", "debug", "security"} and rel.startswith(".agents/skills/"):
        score -= 6
    preview = _safe_read(path, max_bytes=2_000).lower()
    for term in query_terms:
        if term in rel.lower():
            score += 4
        elif term in preview:
            score += 1
    if repo_facts.get("has_tests_dir") and rel.startswith("tests/"):
        score += 1
    return score


def _iter_text_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix not in TEXT_SUFFIXES:
            continue
        if ".autoresearch/runs/" in path.as_posix():
            continue
        files.append(path)
    return files


def _is_context_candidate(rel: str, workflow: Workflow) -> bool:
    blocked_prefixes = [".autoresearch/runs/"]
    if workflow in {"plan", "debug", "security", "ship"}:
        blocked_prefixes.extend(
            [
                ".agents/skills/",
                "test-fixtures/",
            ]
        )
    if workflow == "ship":
        blocked_prefixes.extend(
            [
                ".autoresearch/targets/",
                "scripts/smoke/",
                "tests/",
                "src/",
            ]
        )
    for prefix in blocked_prefixes:
        if rel.startswith(prefix):
            return False
    return True


def _read_excerpt(path: Path) -> tuple[str, bool]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    excerpted = False
    if len(lines) > MAX_FILE_LINES:
        lines = lines[:MAX_FILE_LINES]
        excerpted = True
    excerpt = "\n".join(lines)
    if len(excerpt.encode("utf-8")) > MAX_FILE_BYTES:
        excerpt = excerpt.encode("utf-8")[:MAX_FILE_BYTES].decode("utf-8", errors="ignore")
        excerpted = True
    if excerpted:
        excerpt = excerpt.rstrip() + "\n\n# excerpted by autoresearch context builder\n"
    elif not excerpt.endswith("\n"):
        excerpt += "\n"
    return excerpt, excerpted


def _safe_read(path: Path, *, max_bytes: int) -> str:
    data = path.read_bytes()[:max_bytes]
    return data.decode("utf-8", errors="ignore")


def _tests_use_unittest(repo_root: Path) -> bool:
    tests_dir = repo_root / "tests"
    if not tests_dir.exists():
        return False
    for path in _iter_text_files(tests_dir):
        preview = _safe_read(path, max_bytes=1_500)
        if "import unittest" in preview or "unittest.TestCase" in preview:
            return True
    return False


def _tests_use_pytest(repo_root: Path) -> bool:
    if (repo_root / "pytest.ini").exists():
        return True
    if (repo_root / "pyproject.toml").exists() and "pytest" in _safe_read(repo_root / "pyproject.toml", max_bytes=4_000).lower():
        return True
    tests_dir = repo_root / "tests"
    if not tests_dir.exists():
        return False
    for path in _iter_text_files(tests_dir):
        preview = _safe_read(path, max_bytes=1_500)
        if "import pytest" in preview or "@pytest" in preview:
            return True
    return False


def _explicit_scope_globs(text: str) -> list[str]:
    globs = re.findall(r"([A-Za-z0-9_.\-/]+\*\*?)", text)
    cleaned = [item.strip() for item in globs if "/" in item or "*" in item]
    unique: list[str] = []
    for item in cleaned:
        if item not in unique:
            unique.append(item)
    return unique[:4]


def _choose_metric_candidate(goal: str, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    lowered = goal.lower()
    for candidate in candidates:
        if "coverage" in lowered or "regression" in lowered or "test" in lowered:
            if candidate["name"] == "test_count":
                return candidate
    return candidates[0]


def _render_context_summary(
    *,
    workflow: Workflow,
    request_text: str,
    repo_facts: dict[str, Any],
    candidate_verify_commands: list[str],
    candidate_scope_globs: list[str],
    metric_candidates: list[dict[str, Any]],
    selected_files: list[ContextFile],
) -> str:
    heading = {
        "plan": "planning",
        "debug": "investigation",
        "security": "risk review",
        "ship": "release readiness",
    }.get(workflow, workflow)
    lines = [
        f"# {heading} context summary",
        "",
        f"- request: {request_text}",
        f"- repo name: {repo_facts['repo_name']}",
        f"- manifests: {', '.join(repo_facts['manifests']) or '(none)'}",
        f"- top-level entries: {', '.join(repo_facts['top_level_entries']) or '(none)'}",
        f"- tests dir: {'yes' if repo_facts['has_tests_dir'] else 'no'}",
        f"- src dir: {'yes' if repo_facts['has_src_dir'] else 'no'}",
        f"- unittest detected: {'yes' if repo_facts['has_unittest'] else 'no'}",
        f"- pytest detected: {'yes' if repo_facts['has_pytest'] else 'no'}",
        "",
        "The runner already pre-selected the relevant repository context.",
        "Use this summary and the copied `files/` tree as authoritative inputs.",
        "The files listed below are copied into `files/` and may be opened directly if needed.",
        "Do not execute repository commands outside that bounded `files/` tree.",
        "",
        "## Candidate verify commands",
    ]
    if candidate_verify_commands:
        if workflow in {"debug", "security", "ship"}:
            lines.append("_Metadata only — not intended to be executed from this context workspace._")
        lines.extend(f"- `{command}`" for command in candidate_verify_commands)
    else:
        lines.append("- none inferred")
    if workflow == "plan":
        lines.extend(["", "## Candidate scopes"])
        if candidate_scope_globs:
            lines.extend(f"- `{item}`" for item in candidate_scope_globs)
        else:
            lines.append("- none inferred")
        lines.extend(["", "## Candidate metrics"])
        if metric_candidates:
            for item in metric_candidates:
                lines.append(
                    f"- `{item['name']}` ({item['direction']}) via `{item['extractor']['type']}` `{item['extractor']['value']}`"
                )
        else:
            lines.append("- none inferred")
    lines.extend(["", "## Selected files"])
    if selected_files:
        for item in selected_files:
            suffix = " (excerpted)" if item.excerpted else ""
            lines.append(f"- `{item.context_path}` from `{item.source_path}`{suffix}")
    else:
        lines.append("- none selected")
    lines.append("")
    lines.append("Use only this summary plus files in `files/`. Do not perform broad repository discovery.")
    return "\n".join(lines).rstrip() + "\n"


def _fallback_next_steps(workflow: Workflow, context_packet: ContextPacket) -> str:
    if workflow == "debug":
        return "Re-run the debug workflow with a narrower summary, or inspect the selected source/test files and failing verify logs manually."
    if workflow == "security":
        return "Review the selected manifests and source files for subprocess, secret, and dependency handling, then rerun with a narrower security summary if needed."
    if workflow == "ship":
        return "Use the selected release docs/scripts to complete a manual readiness review, then rerun with a narrower release question if you need model help."
    return "Refine the request and retry."
