#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "test-fixtures"


def run(cmd: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(["/bin/zsh", "-lc", cmd], cwd=cwd, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed ({cmd})\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    return proc


def init_git_repo(path: Path) -> None:
    run("git init -q", path)
    run('git config user.name "Smoke Tester"', path)
    run('git config user.email "smoke@example.com"', path)
    run("git add .", path)
    run('git commit -qm "fixture baseline"', path)


def load_fixture(path: Path) -> dict:
    return json.loads((path / "fixture.json").read_text(encoding="utf-8"))


def check_fixture(path: Path) -> None:
    fixture = load_fixture(path)
    with tempfile.TemporaryDirectory(prefix=f"autoresearch-smoke-{path.name}-") as temp_dir:
        workdir = Path(temp_dir) / path.name
        shutil.copytree(path, workdir)

        if fixture.get("init_git"):
            init_git_repo(workdir)

        dirty = fixture.get("dirty_worktree")
        if dirty:
            target = workdir / dirty["path"]
            target.write_text(target.read_text(encoding="utf-8") + dirty.get("append", "\n# dirty change\n"), encoding="utf-8")
            status = run("git status --porcelain", workdir)
            if not status.stdout.strip():
                raise RuntimeError(f"{path.name}: expected dirty worktree after applying dirty_worktree change")

        for required in fixture.get("required_paths", []):
            if not (workdir / required).exists():
                raise RuntimeError(f"{path.name}: missing required path {required}")

        command = fixture.get("verify_command")
        expected_exit = fixture.get("expected_exit")
        if command is not None and expected_exit is not None:
            proc = run(command, workdir, check=False)
            if proc.returncode != expected_exit:
                raise RuntimeError(
                    f"{path.name}: expected exit {expected_exit} but got {proc.returncode}\n"
                    f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
                )


def main() -> int:
    run("uv run python scripts/validate-codex-assets.py", ROOT)
    run("uv run python -m unittest discover -s tests -v", ROOT)
    fixture_paths = sorted(p for p in FIXTURES.iterdir() if p.is_dir() and (p / "fixture.json").exists())
    for fixture_path in fixture_paths:
        check_fixture(fixture_path)
        print(f"smoke passed: {fixture_path.name}")
    print("smoke suite passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
