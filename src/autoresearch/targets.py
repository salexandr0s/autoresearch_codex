from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .errors import ValidationError
from .models import CommandConfig, MetricConfig, MetricExtractor, ScopeConfig, StoppingConfig, TargetConfig
from .pathing import resolve_repo_path


def _require_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"missing or invalid {key}")
    return value.strip()


def load_target(path: Path) -> TargetConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValidationError(f"target file {path} must be a mapping")
    return parse_target(raw, path=path)


def parse_target(raw: dict[str, Any], path: Path | None = None) -> TargetConfig:
    name = _require_string(raw, "name")
    goal = _require_string(raw, "goal")

    scope_raw = raw.get("scope")
    if not isinstance(scope_raw, dict):
        raise ValidationError("missing scope block")
    include = scope_raw.get("include")
    exclude = scope_raw.get("exclude", [])
    if not isinstance(include, list) or not include or not all(isinstance(item, str) and item for item in include):
        raise ValidationError("scope.include must contain at least one glob")
    if not isinstance(exclude, list) or not all(isinstance(item, str) for item in exclude):
        raise ValidationError("scope.exclude must be a list of globs")
    scope = ScopeConfig(include=[item.strip() for item in include], exclude=[item.strip() for item in exclude])

    metric_raw = raw.get("metric")
    if not isinstance(metric_raw, dict):
        raise ValidationError("missing metric block")
    metric_name = _require_string(metric_raw, "name")
    direction = metric_raw.get("direction")
    if direction not in {"higher", "lower"}:
        raise ValidationError("metric.direction must be 'higher' or 'lower'")
    extractor_raw = metric_raw.get("extractor")
    if not isinstance(extractor_raw, dict):
        raise ValidationError("missing metric.extractor block")
    extractor_type = extractor_raw.get("type")
    if extractor_type not in {"regex", "jsonpath", "script"}:
        raise ValidationError("metric.extractor.type must be regex, jsonpath, or script")
    extractor_value = _require_string(extractor_raw, "value")
    metric = MetricConfig(metric_name, direction, MetricExtractor(extractor_type, extractor_value))

    verify_raw = raw.get("verify")
    if not isinstance(verify_raw, dict):
        raise ValidationError("missing verify block")
    verify = CommandConfig(_require_string(verify_raw, "command"))

    guard_raw = raw.get("guard")
    guard = None
    if guard_raw is not None:
        if not isinstance(guard_raw, dict):
            raise ValidationError("guard must be a mapping when present")
        command = guard_raw.get("command")
        if command is not None and (not isinstance(command, str) or not command.strip()):
            raise ValidationError("guard.command must be a non-empty string when present")
        if isinstance(command, str) and command.strip():
            guard = CommandConfig(command.strip())

    stopping_raw = raw.get("stopping")
    if not isinstance(stopping_raw, dict):
        raise ValidationError("missing stopping block")
    stopping = StoppingConfig(
        max_iterations=_positive_int(stopping_raw, "max_iterations"),
        goal_threshold=_optional_float(stopping_raw.get("goal_threshold")),
        stagnation_reflect_after=_positive_int(stopping_raw, "stagnation_reflect_after"),
        stop_after_consecutive_failures=_positive_int(stopping_raw, "stop_after_consecutive_failures"),
    )

    return TargetConfig(name, goal, scope, metric, verify, guard, stopping, path=path)


def dump_target(target: TargetConfig) -> str:
    return yaml.safe_dump(target.to_dict(), sort_keys=False)


def _positive_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or value <= 0:
        raise ValidationError(f"{key} must be a positive integer")
    return value


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raise ValidationError("goal_threshold must be numeric when present")


def resolve_target_path(repo_root: Path, explicit: str | None) -> Path:
    return resolve_repo_path(repo_root, explicit or ".autoresearch/targets/default.yaml", purpose="target path")
