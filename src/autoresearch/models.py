from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

Decision = Literal["baseline", "keep", "discard", "crash", "inconclusive", "blocked"]
Workflow = Literal["plan", "loop", "debug", "fix", "security", "ship", "skill-optimize"]
CompletionMode = Literal["model", "fallback"]


@dataclass(slots=True)
class MetricExtractor:
    type: Literal["regex", "jsonpath", "script"]
    value: str


@dataclass(slots=True)
class MetricConfig:
    name: str
    direction: Literal["higher", "lower"]
    extractor: MetricExtractor


@dataclass(slots=True)
class ScopeConfig:
    include: list[str]
    exclude: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CommandConfig:
    command: str


@dataclass(slots=True)
class StoppingConfig:
    max_iterations: int
    goal_threshold: float | None = None
    stagnation_reflect_after: int = 5
    stop_after_consecutive_failures: int = 10


@dataclass(slots=True)
class TargetConfig:
    name: str
    goal: str
    scope: ScopeConfig
    metric: MetricConfig
    verify: CommandConfig
    guard: CommandConfig | None
    stopping: StoppingConfig
    path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("path", None)
        return data


@dataclass(slots=True)
class BackendResult:
    exit_code: int
    stdout: str
    stderr: str
    final_message: str
    command: list[str]
    duration_seconds: float
    timed_out: bool = False


@dataclass(slots=True)
class RunPaths:
    root: Path
    iterations_dir: Path
    artifacts_dir: Path
    context_dir: Path
    schemas_dir: Path
    target_file: Path
    baseline_file: Path
    results_file: Path
    summary_file: Path
    engine_file: Path


@dataclass(slots=True)
class RepoState:
    root: Path
    branch: str
    head: str
    dirty: bool


@dataclass(slots=True)
class EngineState:
    run_id: str
    workflow: Workflow
    target_repo: str
    source_branch: str
    source_head: str
    run_branch: str
    worktree_path: str
    codex_bin: str
    model: str | None
    profile: str | None
    search: bool
    target_path: str | None
    status: str
    created_at: str
    updated_at: str
    resumable: bool
    latest_iteration: int = 0
    best_metric: float | None = None
    best_iteration: int | None = None
    baseline_metric: float | None = None
    warning: str | None = None
    workspace_kind: str = "worktree"
    deadline_seconds: int | None = None
    duration_seconds: float | None = None
    timed_out: bool = False
    completion_mode: CompletionMode = "model"
    prompt_bytes: int = 0
    context_bytes: int = 0
    selected_file_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class IterationContext:
    iteration: int
    hypothesis: str
    prompt_file: Path
    final_message_file: Path
    verify_log_file: Path
    guard_log_file: Path
    agent_jsonl_file: Path


@dataclass(slots=True)
class ResultRow:
    iteration: int
    timestamp: str
    branch: str
    commit: str
    revert_commit: str
    metric: str
    best_metric: str
    delta_from_best: str
    verify_status: str
    guard_status: str
    decision: Decision
    hypothesis: str
    files_touched: str
    artifact_path: str
    decision_reason: str

    @classmethod
    def header(cls) -> list[str]:
        return [
            "iteration",
            "timestamp",
            "branch",
            "commit",
            "revert_commit",
            "metric",
            "best_metric",
            "delta_from_best",
            "verify_status",
            "guard_status",
            "decision",
            "hypothesis",
            "files_touched",
            "artifact_path",
            "decision_reason",
        ]

    def to_tsv(self) -> str:
        values = [getattr(self, name) for name in self.header()]
        return "\t".join(str(v) for v in values)
