from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
import re

from .models import EngineState, ResultRow, RunPaths, TargetConfig
from .pathing import resolve_run_dir
from .targets import dump_target, load_target


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_now() -> str:
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_run_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "run"
    return utc_now().strftime("%Y-%m-%dT%H%M%SZ") + f"-{slug}"


def make_run_paths(repo_root: Path, run_id: str) -> RunPaths:
    root = resolve_run_dir(repo_root, run_id)
    iterations = root / "iterations"
    artifacts = root / "artifacts"
    context = root / "context"
    schemas = root / "schemas"
    root.mkdir(parents=True, exist_ok=True)
    iterations.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)
    context.mkdir(parents=True, exist_ok=True)
    schemas.mkdir(parents=True, exist_ok=True)
    return RunPaths(
        root=root,
        iterations_dir=iterations,
        artifacts_dir=artifacts,
        context_dir=context,
        schemas_dir=schemas,
        target_file=root / "target.yaml",
        baseline_file=root / "baseline.json",
        results_file=root / "results.tsv",
        summary_file=root / "summary.md",
        engine_file=root / "engine.json",
    )


def write_target_snapshot(paths: RunPaths, target: TargetConfig) -> None:
    paths.target_file.write_text(dump_target(target), encoding="utf-8")


def load_target_snapshot(paths: RunPaths) -> TargetConfig:
    return load_target(paths.target_file)


def write_engine(paths: RunPaths, engine: EngineState) -> None:
    payload = engine.to_dict()
    paths.engine_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_engine(run_dir: Path) -> EngineState:
    payload = json.loads((run_dir / "engine.json").read_text(encoding="utf-8"))
    return EngineState(**payload)


def write_baseline(paths: RunPaths, baseline: dict) -> None:
    paths.baseline_file.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def init_results(paths: RunPaths) -> None:
    if paths.results_file.exists():
        return
    header = "\t".join(ResultRow.header())
    paths.results_file.write_text(header + "\n", encoding="utf-8")


def append_result(paths: RunPaths, row: ResultRow) -> None:
    with paths.results_file.open("a", encoding="utf-8") as handle:
        handle.write(row.to_tsv() + "\n")


def read_results(paths: RunPaths) -> list[dict[str, str]]:
    if not paths.results_file.exists():
        return []
    with paths.results_file.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [dict(row) for row in reader]


def latest_run_dir(repo_root: Path) -> Path | None:
    runs_root = repo_root / ".autoresearch" / "runs"
    if not runs_root.exists():
        return None
    run_dirs = [path for path in runs_root.iterdir() if path.is_dir()]
    if not run_dirs:
        return None
    return sorted(run_dirs)[-1]


def write_summary(paths: RunPaths, summary: str) -> None:
    paths.summary_file.write_text(summary.rstrip() + "\n", encoding="utf-8")


def format_recent_results(rows: list[dict[str, str]], limit: int = 5) -> str:
    if not rows:
        return ""
    recent = rows[-limit:]
    lines = ["iteration | metric | decision | hypothesis", "--- | --- | --- | ---"]
    for row in recent:
        lines.append(
            f"{row.get('iteration','')} | {row.get('metric','')} | {row.get('decision','')} | {row.get('hypothesis','')}"
        )
    return "\n".join(lines)
