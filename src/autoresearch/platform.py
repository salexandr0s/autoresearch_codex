from __future__ import annotations

import importlib.util
import json
import os
import platform as py_platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from .models import TargetConfig


@dataclass(slots=True)
class PlatformReport:
    os_name: str
    arch: str
    is_macos: bool
    is_apple_silicon: bool
    python_version: str
    git_available: bool
    uv_available: bool
    codex_available: bool
    caffeinate_available: bool
    xcode_clt_available: bool | None = None
    torch_importable: bool | None = None
    torch_version: str | None = None
    mps_available: bool | None = None
    cuda_available: bool | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def collect_platform_report(codex_bin: str | None = None) -> PlatformReport:
    os_name = sys.platform
    arch = py_platform.machine().lower()
    is_macos = os_name == "darwin"
    is_apple_silicon = is_macos and arch in {"arm64", "aarch64"}
    torch_info = _probe_torch()
    codex_ref = codex_bin or os.environ.get("AUTORESEARCH_CODEX_BIN") or "codex"
    return PlatformReport(
        os_name=os_name,
        arch=arch,
        is_macos=is_macos,
        is_apple_silicon=is_apple_silicon,
        python_version=py_platform.python_version(),
        git_available=_command_available("git"),
        uv_available=_command_available("uv"),
        codex_available=_command_available(codex_ref),
        caffeinate_available=_command_available("caffeinate"),
        xcode_clt_available=_detect_xcode_clt() if is_macos else None,
        torch_importable=torch_info.get("torch_importable"),
        torch_version=torch_info.get("torch_version"),
        mps_available=torch_info.get("mps_available"),
        cuda_available=torch_info.get("cuda_available"),
    )


def generic_workflow_status(report: PlatformReport) -> str:
    return "supported" if report.git_available and report.uv_available and report.codex_available else "blocked"


def apple_silicon_ml_status(report: PlatformReport) -> str:
    if not report.is_macos or not report.is_apple_silicon:
        return "blocked"
    if report.torch_importable is True and report.mps_available is True:
        return "supported"
    return "best-effort"


def platform_warning_messages(report: PlatformReport) -> list[str]:
    warnings: list[str] = []
    if report.is_macos and not report.is_apple_silicon:
        warnings.append("Intel Mac detected; generic repo workflows are supported, but Apple Silicon ML examples are not first-class on this machine.")
    if report.is_macos and report.torch_importable is True and report.mps_available is False:
        warnings.append("torch is installed but MPS is unavailable; Apple Silicon ML targets may need environment fixes in the target repo.")
    if report.is_macos and report.caffeinate_available is False:
        warnings.append("`caffeinate` was not found; overnight macOS runs may sleep unless you keep the machine awake another way.")
    if report.is_macos and report.xcode_clt_available is False:
        warnings.append("Xcode Command Line Tools were not detected; native package installs and some Python builds may fail on macOS.")
    return warnings


def target_platform_warning_messages(report: PlatformReport, target: TargetConfig) -> list[str]:
    if not report.is_macos:
        return []
    warnings: list[str] = []
    target_text = " ".join(
        [
            target.goal,
            target.verify.command,
            target.metric.name,
            target.metric.extractor.value,
            *(target.scope.include or []),
            *(target.scope.exclude or []),
        ]
    ).lower()
    if any(token in target_text for token in ("cuda", "cudnn", "nvidia")):
        warnings.append("target appears to assume CUDA/NVIDIA-specific tooling; on macOS, portability work usually belongs in the target repo.")
    if target.metric.name.lower() == "peak_vram_mb" or "peak_vram_mb" in target.metric.extractor.value.lower():
        warnings.append("target uses `peak_vram_mb`; on macOS/Apple Silicon, unified-memory reporting is repo-specific and may be a weak acceptance metric.")
    return warnings


def render_platform_messages(report: PlatformReport) -> list[str]:
    messages = [
        f"platform: os={report.os_name} arch={report.arch} python={report.python_version}",
        "tools: "
        f"git={'yes' if report.git_available else 'no'} "
        f"uv={'yes' if report.uv_available else 'no'} "
        f"codex={'yes' if report.codex_available else 'no'} "
        f"caffeinate={'yes' if report.caffeinate_available else 'no'}",
        f"generic repo workflows: {generic_workflow_status(report)}",
        f"Apple Silicon ML workflows: {apple_silicon_ml_status(report)}",
    ]
    if report.is_macos:
        xcode = "yes" if report.xcode_clt_available else "no"
        messages.append(f"xcode command line tools: {xcode}")
    if report.torch_importable is True:
        messages.append(
            "torch: "
            f"version={report.torch_version or 'unknown'} "
            f"mps={'yes' if report.mps_available else 'no'} "
            f"cuda={'yes' if report.cuda_available else 'no'}"
        )
    elif report.torch_importable is False:
        messages.append("torch: not importable in the active Python environment")
    return messages


def _command_available(command: str) -> bool:
    if "/" in command:
        path = Path(command)
        return path.exists() and path.is_file()
    return shutil.which(command) is not None


def _detect_xcode_clt() -> bool:
    try:
        proc = subprocess.run(
            ["xcode-select", "-p"],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0 and bool((proc.stdout or proc.stderr).strip())


def _probe_torch() -> dict[str, object | None]:
    if importlib.util.find_spec("torch") is None:
        return {"torch_importable": False, "torch_version": None, "mps_available": None, "cuda_available": None}
    script = (
        "import json\n"
        "try:\n"
        "    import torch\n"
        "except Exception:\n"
        "    print(json.dumps({'torch_importable': False, 'torch_version': None, 'mps_available': None, 'cuda_available': None}))\n"
        "    raise SystemExit(0)\n"
        "mps = None\n"
        "cuda = None\n"
        "try:\n"
        "    mps = bool(torch.backends.mps.is_available())\n"
        "except Exception:\n"
        "    mps = None\n"
        "try:\n"
        "    cuda = bool(torch.cuda.is_available())\n"
        "except Exception:\n"
        "    cuda = None\n"
        "print(json.dumps({'torch_importable': True, 'torch_version': getattr(torch, '__version__', None), 'mps_available': mps, 'cuda_available': cuda}))\n"
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return {"torch_importable": None, "torch_version": None, "mps_available": None, "cuda_available": None}
    if proc.returncode != 0:
        return {"torch_importable": None, "torch_version": None, "mps_available": None, "cuda_available": None}
    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except json.JSONDecodeError:
        return {"torch_importable": None, "torch_version": None, "mps_available": None, "cuda_available": None}
    return {
        "torch_importable": payload.get("torch_importable"),
        "torch_version": payload.get("torch_version"),
        "mps_available": payload.get("mps_available"),
        "cuda_available": payload.get("cuda_available"),
    }
