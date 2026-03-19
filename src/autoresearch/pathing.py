from __future__ import annotations

import re
from pathlib import Path

from .errors import ValidationError


RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def resolve_repo_path(repo_root: Path, value: str | Path, *, purpose: str) -> Path:
    root = repo_root.resolve()
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValidationError(f"{purpose} escapes repository root: {value}") from exc
    return resolved


def resolve_run_dir(repo_root: Path, run_id: str) -> Path:
    safe_run_id = validate_run_id(run_id)
    runs_root = (repo_root.resolve() / ".autoresearch" / "runs").resolve()
    path = (runs_root / safe_run_id).resolve()
    try:
        path.relative_to(runs_root)
    except ValueError as exc:
        raise ValidationError(f"run id escapes runs directory: {run_id}") from exc
    return path


def validate_run_id(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("run id must be a non-empty string")
    cleaned = value.strip()
    if "/" in cleaned or "\\" in cleaned or cleaned in {".", ".."}:
        raise ValidationError("run id must be a single safe path segment")
    if not RUN_ID_PATTERN.fullmatch(cleaned):
        raise ValidationError("run id must contain only letters, numbers, dots, underscores, and dashes")
    return cleaned


def resolve_release_output_path(repo_root: Path, value: str) -> Path:
    root = repo_root.resolve()
    dist_root = (root / "dist").resolve()
    path = Path(value)
    if path.is_absolute():
        raise ValidationError("release output path must be relative and stay under dist/")
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(dist_root)
    except ValueError as exc:
        raise ValidationError("release output path must stay under dist/") from exc
    if resolved == dist_root:
        raise ValidationError("release output path must be a subdirectory under dist/")
    return resolved
