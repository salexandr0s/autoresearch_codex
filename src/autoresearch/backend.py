from __future__ import annotations

import os
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import TextIO

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
    deadline_seconds: int | None = None,
    skip_git_repo_check: bool = False,
    output_schema_file: Path | None = None,
    sandbox_mode: str = "workspace-write",
) -> BackendResult:
    final_message_file.parent.mkdir(parents=True, exist_ok=True)
    agent_jsonl_file.parent.mkdir(parents=True, exist_ok=True)

    command = [codex_bin, "-a", "never", "-s", sandbox_mode, "exec", "-C", str(cwd), "-o", str(final_message_file), "--json"]
    if skip_git_repo_check:
        command.append("--skip-git-repo-check")
    if output_schema_file:
        command.extend(["--output-schema", str(output_schema_file)])
    if model:
        command.extend(["--model", model])
    if profile:
        command.extend(["--profile", profile])
    if search:
        command.append("--search")

    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    stream_lock = threading.Lock()
    start = time.monotonic()

    def pump(pipe: TextIO | None, sink_path: Path | None, parts: list[str]) -> None:
        if pipe is None:
            return
        sink = sink_path.open("a", encoding="utf-8") if sink_path else None
        try:
            for chunk in pipe:
                parts.append(chunk)
                if sink:
                    with stream_lock:
                        sink.write(chunk)
                        sink.flush()
        finally:
            if sink:
                sink.close()
            pipe.close()

    agent_jsonl_file.write_text("", encoding="utf-8")
    proc = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        start_new_session=True,
    )

    if proc.stdin is None:
        raise BlockedRunError("failed to open Codex stdin")
    proc.stdin.write(prompt)
    proc.stdin.close()

    stdout_thread = threading.Thread(target=pump, args=(proc.stdout, agent_jsonl_file, stdout_parts), daemon=True)
    stderr_thread = threading.Thread(target=pump, args=(proc.stderr, None, stderr_parts), daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    timed_out = False
    try:
        proc.wait(timeout=deadline_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate_process_group(proc)

    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)
    if proc.poll() is None:
        _kill_process_group(proc)
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)

    duration_seconds = time.monotonic() - start
    final_message = final_message_file.read_text(encoding="utf-8") if final_message_file.exists() else ""
    return BackendResult(
        exit_code=proc.returncode if proc.returncode is not None else 1,
        stdout="".join(stdout_parts),
        stderr="".join(stderr_parts),
        final_message=final_message,
        command=command,
        duration_seconds=duration_seconds,
        timed_out=timed_out,
    )


def _terminate_process_group(proc: subprocess.Popen[str]) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _kill_process_group(proc)


def _kill_process_group(proc: subprocess.Popen[str]) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
