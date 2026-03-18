from __future__ import annotations

import fnmatch
import subprocess
import tempfile
from pathlib import Path

from .errors import BlockedRunError, ValidationError
from .models import RepoState, ScopeConfig

IGNORED_CHANGED_PATH_PATTERNS = (
    "__pycache__",
    "__pycache__/*",
    "*.pyc",
    ".pytest_cache",
    ".pytest_cache/*",
    ".mypy_cache",
    ".mypy_cache/*",
    ".ruff_cache",
    ".ruff_cache/*",
    ".autoresearch/runs",
    ".autoresearch/runs/*",
)


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        text=True,
        capture_output=True,
        check=False,
    )
    if check and proc.returncode != 0:
        raise BlockedRunError(proc.stderr.strip() or proc.stdout.strip() or f"git {' '.join(args)} failed")
    return proc


def inspect_repo(repo: Path) -> RepoState:
    inside = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=str(repo), text=True, capture_output=True)
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        raise BlockedRunError(f"{repo} is not a git repository")
    root = Path(git(repo, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    branch = git(root, "branch", "--show-current").stdout.strip() or "HEAD"
    head = git(root, "rev-parse", "HEAD").stdout.strip()
    dirty = bool(git(root, "status", "--porcelain", check=False).stdout.strip())
    return RepoState(root=root, branch=branch, head=head, dirty=dirty)


def branch_exists(repo: Path, branch: str) -> bool:
    proc = git(repo, "show-ref", "--verify", f"refs/heads/{branch}", check=False)
    return proc.returncode == 0


def ensure_worktree(repo: Path, branch: str, run_id: str, existing_path: str | None = None) -> Path:
    if existing_path:
        path = Path(existing_path)
        if path.exists():
            return path
    worktree_path = Path(tempfile.mkdtemp(prefix=f"autoresearch-{run_id}-"))
    if branch_exists(repo, branch):
        git(repo, "worktree", "add", str(worktree_path), branch)
    else:
        git(repo, "worktree", "add", "-b", branch, str(worktree_path), "HEAD")
    return worktree_path


def changed_files(repo: Path) -> list[str]:
    proc = git(repo, "status", "--porcelain", check=False)
    files: list[str] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        candidate = line[3:].strip()
        if any(_match(candidate, pattern) for pattern in IGNORED_CHANGED_PATH_PATTERNS):
            continue
        files.append(candidate)
    return files


def files_within_scope(files: list[str], scope: ScopeConfig) -> bool:
    if not files:
        return False
    for file in files:
        if not matches_scope(file, scope):
            return False
    return True


def matches_scope(path: str, scope: ScopeConfig) -> bool:
    included = any(_match(path, pattern) for pattern in scope.include)
    excluded = any(_match(path, pattern) for pattern in scope.exclude)
    return included and not excluded


def _match(path: str, pattern: str) -> bool:
    return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, pattern.replace("**", "*"))


def commit_all(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)
    return git(repo, "rev-parse", "--short", "HEAD").stdout.strip()


def revert_head(repo: Path) -> str:
    git(repo, "revert", "--no-edit", "HEAD")
    return git(repo, "rev-parse", "--short", "HEAD").stdout.strip()


def current_short_commit(repo: Path) -> str:
    return git(repo, "rev-parse", "--short", "HEAD").stdout.strip()


def current_branch(repo: Path) -> str:
    return git(repo, "branch", "--show-current").stdout.strip() or "HEAD"


def assert_worktree_clean(repo: Path) -> None:
    if changed_files(repo):
        raise ValidationError("worktree is not clean when a clean state is required")
