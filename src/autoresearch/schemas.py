from __future__ import annotations

import json
from pathlib import Path

from .models import Workflow


def write_plan_output_schema(path: Path) -> Path:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["name", "goal", "scope", "metric", "verify", "guard", "stopping"],
        "properties": {
            "name": {"type": "string"},
            "goal": {"type": "string"},
            "scope": {
                "type": "object",
                "additionalProperties": False,
                "required": ["include", "exclude"],
                "properties": {
                    "include": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                    "exclude": {"type": "array", "items": {"type": "string"}},
                },
            },
            "metric": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "direction", "extractor"],
                "properties": {
                    "name": {"type": "string"},
                    "direction": {"type": "string", "enum": ["higher", "lower"]},
                    "extractor": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["type", "value"],
                        "properties": {
                            "type": {"type": "string", "enum": ["regex", "jsonpath", "script"]},
                            "value": {"type": "string"},
                        },
                    },
                },
            },
            "verify": {
                "type": "object",
                "additionalProperties": False,
                "required": ["command"],
                "properties": {"command": {"type": "string"}},
            },
            "guard": {
                "anyOf": [
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["command"],
                        "properties": {"command": {"type": "string"}},
                    },
                    {"type": "null"},
                ],
            },
            "stopping": {
                "type": "object",
                "additionalProperties": False,
                "required": ["max_iterations", "goal_threshold", "stagnation_reflect_after", "stop_after_consecutive_failures"],
                "properties": {
                    "max_iterations": {"type": "integer", "minimum": 1},
                    "goal_threshold": {"type": ["number", "null"]},
                    "stagnation_reflect_after": {"type": "integer", "minimum": 1},
                    "stop_after_consecutive_failures": {"type": "integer", "minimum": 1},
                },
            },
        },
    }
    return _write_schema(path, schema)


def write_report_output_schema(path: Path, workflow: Workflow) -> Path:
    if workflow == "ship":
        return _write_schema(path, _ship_schema())
    return _write_schema(path, _finding_report_schema())


def _finding_report_schema() -> dict:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["title", "summary", "findings", "artifact_markdown"],
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["id", "title", "severity", "evidence", "recommendation"],
                    "properties": {
                        "id": {"type": "string"},
                        "title": {"type": "string"},
                        "severity": {"type": "string"},
                        "evidence": {"type": "string"},
                        "recommendation": {"type": "string"},
                    },
                },
            },
            "artifact_markdown": {"type": "string"},
        },
    }
    return schema


def _ship_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["title", "summary", "checklist_markdown", "release_plan_markdown"],
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "checklist_markdown": {"type": "string"},
            "release_plan_markdown": {"type": "string"},
        },
    }


def _write_schema(path: Path, schema: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
