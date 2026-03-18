from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .errors import BlockedRunError
from .models import BackendResult


def resolve_codex_bin(explicit: str | None = None) -> str:
    candidate = explicit or os.environ.get("AUTORESEARCH_CODEX_BIN") or "codex"
    resolved = shutil.which(candidate)
    if not resolved:
        raise BlockedRunError(f"Codex CLI not found: {candidate}")
    return resolved


def run_codex(
    *,
    codex_bin: str,
    cwd: Path,
    prompt: str,
    final_message_file: Path,
    agent_jsonl_file: Path,
    model: str | None = None,
    profile: str | None = None,
    search: bool = False,
) -> BackendResult:
    final_message_file.parent.mkdir(parents=True, exist_ok=True)
    command = [codex_bin, "-a", "never", "-s", "workspace-write", "exec", "-C", str(cwd), "-o", str(final_message_file), "--json"]
    if model:
        command.extend(["--model", model])
    if profile:
        command.extend(["--profile", profile])
    if search:
        command.append("--search")

    proc = subprocess.run(
        command,
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
    )
    agent_jsonl_file.parent.mkdir(parents=True, exist_ok=True)
    agent_jsonl_file.write_text(proc.stdout or "", encoding="utf-8")
    final_message = final_message_file.read_text(encoding="utf-8") if final_message_file.exists() else ""
    return BackendResult(
        exit_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        final_message=final_message,
        command=command,
    )
