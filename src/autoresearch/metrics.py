from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .errors import ValidationError
from .models import MetricExtractor


def extract_metric(extractor: MetricExtractor, text: str, cwd: Path, log_path: Path) -> float:
    if extractor.type == "regex":
        return _extract_regex(extractor.value, text)
    if extractor.type == "jsonpath":
        return _extract_jsonpath(extractor.value, text)
    if extractor.type == "script":
        return _extract_script(extractor.value, cwd, log_path)
    raise ValidationError(f"unsupported extractor type: {extractor.type}")


def _extract_regex(pattern: str, text: str) -> float:
    match = re.search(pattern, text, re.M)
    if not match:
        raise ValidationError(f"metric regex did not match: {pattern}")
    value = match.group(1) if match.groups() else match.group(0)
    try:
        return float(value)
    except ValueError as exc:
        raise ValidationError(f"regex extractor did not yield a numeric value: {value}") from exc


def _extract_jsonpath(expr: str, text: str) -> float:
    try:
        from jsonpath_ng.ext import parse as parse_jsonpath
    except ImportError as exc:
        raise ValidationError("jsonpath-ng is required for jsonpath metric extractors") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError("verify output is not valid JSON for jsonpath extraction") from exc
    matches = parse_jsonpath(expr).find(payload)
    if not matches:
        raise ValidationError(f"jsonpath extractor did not match: {expr}")
    value = matches[0].value
    if not isinstance(value, (int, float)):
        raise ValidationError(f"jsonpath extractor did not yield a numeric value: {value!r}")
    return float(value)


def _extract_script(script: str, cwd: Path, log_path: Path) -> float:
    script_path = Path(script)
    if not script_path.is_absolute():
        script_path = (cwd / script_path).resolve()
    proc = subprocess.run(
        [str(script_path), str(log_path)],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ValidationError(f"metric script failed: {proc.stderr.strip() or proc.stdout.strip()}")
    value = (proc.stdout or "").strip().splitlines()[-1] if (proc.stdout or "").strip() else ""
    try:
        return float(value)
    except ValueError as exc:
        raise ValidationError(f"metric script did not print a numeric value: {value!r}") from exc
