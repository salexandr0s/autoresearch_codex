#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SKILLS = {
    "autoresearch-loop",
    "autoresearch-plan",
    "autoresearch-debug",
    "autoresearch-fix",
    "autoresearch-security",
    "autoresearch-ship",
}
TEXT_SUFFIXES = {".md", ".toml", ".yaml", ".yml", ".json", ".rules", ".py", ".sh"}
FORBIDDEN_STRINGS = [
    ".claude/",
    "AskUserQuestion",
    "ToolSearch",
    "claude -p",
    "@anthropic-ai/claude-code",
]
FORBIDDEN_SCAN_EXCLUDES = {
    Path("buildplan.md"),
    Path("architecture.md"),
    Path("checklist.md"),
    Path("docs/migration/from-claude.md"),
    Path("legacy/claude/README.md"),
    Path("scripts/validate-codex-assets.py"),
}

errors: list[str] = []


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def fail(message: str) -> None:
    errors.append(message)


def require_exists(path_str: str) -> Path:
    path = ROOT / path_str
    if not path.exists():
        fail(f"missing required path: {path_str}")
    return path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        return {}
    result: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def extract_yaml_block(text: str, key: str) -> str:
    match = re.search(rf"(?m)^{re.escape(key)}:[^\n]*\n((?:^(?:  .*)\n?)*)", text)
    return match.group(1) if match else ""


def validate_positive_int(block: str, field: str, path: Path) -> None:
    match = re.search(rf"^  {re.escape(field)}:\s*(\d+)\s*$", block, re.M)
    if not match:
        fail(f"{rel(path)}: missing or invalid stopping.{field}")
        return
    if int(match.group(1)) <= 0:
        fail(f"{rel(path)}: stopping.{field} must be > 0")


def validate_target_file(path: Path) -> None:
    text = read_text(path)
    if not re.search(r"^name:\s*\S", text, re.M):
        fail(f"{rel(path)}: missing top-level name")
    if not re.search(r"^goal:\s*\S", text, re.M):
        fail(f"{rel(path)}: missing top-level goal")

    scope_block = extract_yaml_block(text, "scope")
    if not scope_block:
        fail(f"{rel(path)}: missing scope block")
    else:
        if not re.search(r"^  include:\s*$", scope_block, re.M):
            fail(f"{rel(path)}: missing scope.include")
        if not re.search(r"^    -\s+.+$", scope_block, re.M):
            fail(f"{rel(path)}: scope.include must contain at least one glob")

    metric_block = extract_yaml_block(text, "metric")
    if not metric_block:
        fail(f"{rel(path)}: missing metric block")
    else:
        if not re.search(r"^  name:\s*\S", metric_block, re.M):
            fail(f"{rel(path)}: missing metric.name")
        direction = re.search(r"^  direction:\s*(higher|lower)\s*$", metric_block, re.M)
        if not direction:
            fail(f"{rel(path)}: metric.direction must be higher or lower")
        extractor_block = re.search(r"(?m)^  extractor:[^\n]*\n((?:^(?:    .*)\n?)*)", metric_block)
        if not extractor_block:
            fail(f"{rel(path)}: missing metric.extractor block")
        else:
            nested = extractor_block.group(1)
            if not re.search(r"^    type:\s*(regex|jsonpath|script)\s*$", nested, re.M):
                fail(f"{rel(path)}: metric.extractor.type must be regex, jsonpath, or script")
            if not re.search(r"^    value:\s*.+$", nested, re.M):
                fail(f"{rel(path)}: missing metric.extractor.value")

    verify_block = extract_yaml_block(text, "verify")
    if not verify_block or not re.search(r"^  command:\s*.+$", verify_block, re.M):
        fail(f"{rel(path)}: missing verify.command")

    guard_block = extract_yaml_block(text, "guard")
    if guard_block and not re.search(r"^  command:\s*.+$", guard_block, re.M):
        fail(f"{rel(path)}: guard block present without guard.command")

    stopping_block = extract_yaml_block(text, "stopping")
    if not stopping_block:
        fail(f"{rel(path)}: missing stopping block")
    else:
        validate_positive_int(stopping_block, "max_iterations", path)
        validate_positive_int(stopping_block, "stagnation_reflect_after", path)
        validate_positive_int(stopping_block, "stop_after_consecutive_failures", path)


def validate_markdown_links(path: Path) -> None:
    text = read_text(path)
    for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
        target = match.group(1).strip()
        if not target or target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = target.split("#", 1)[0]
        resolved = (path.parent / target).resolve()
        try:
            resolved.relative_to(ROOT)
        except ValueError:
            fail(f"{rel(path)}: link escapes repo: {target}")
            continue
        if not resolved.exists():
            fail(f"{rel(path)}: broken link target: {target}")


def validate_skill_dir(skill_dir: Path) -> None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        fail(f"missing SKILL.md in {rel(skill_dir)}")
        return
    frontmatter = parse_frontmatter(read_text(skill_md))
    if not frontmatter.get("name"):
        fail(f"{rel(skill_md)}: missing frontmatter name")
    if not frontmatter.get("description"):
        fail(f"{rel(skill_md)}: missing frontmatter description")


def scan_for_forbidden_strings(path: Path) -> None:
    relative = path.relative_to(ROOT)
    if relative in FORBIDDEN_SCAN_EXCLUDES:
        return
    if relative.parts and relative.parts[0] == "legacy":
        return
    if relative.parts and relative.parts[0] == "bootstrap":
        return
    text = read_text(path)
    for needle in FORBIDDEN_STRINGS:
        if needle in text:
            fail(f"{rel(path)}: contains forbidden legacy string {needle!r}")


def main() -> int:
    require_exists("AGENTS.md")
    require_exists("README.md")
    require_exists("CONTRIBUTING.md")
    require_exists("pyproject.toml")
    config = require_exists(".codex/config.toml")
    require_exists(".autoresearch/targets/default.yaml")
    require_exists("codex/rules/safety.rules")
    require_exists("scripts/release.sh")
    require_exists("scripts/smoke/run.py")
    require_exists("src/autoresearch/cli.py")
    require_exists("src/autoresearch/engine.py")
    require_exists("tests/test_runtime.py")

    if config.exists():
        config_text = read_text(config)
        if 'project_root_markers = [".git", "AGENTS.md"]' not in config_text:
            fail(".codex/config.toml: project_root_markers must include .git and AGENTS.md")

    skills_root = require_exists(".agents/skills")
    if skills_root.exists():
        existing_skills = {p.name for p in skills_root.iterdir() if p.is_dir()}
        missing = sorted(REQUIRED_SKILLS - existing_skills)
        for name in missing:
            fail(f"missing required skill directory: .agents/skills/{name}")
        for skill_name in sorted(existing_skills):
            validate_skill_dir(skills_root / skill_name)

    for path in [ROOT / ".autoresearch/targets/default.yaml", *sorted((ROOT / "test-fixtures").glob("*/.autoresearch/targets/*.yaml"))]:
        if path.exists():
            validate_target_file(path)

    for path in ROOT.rglob("*.md"):
        if "/.autoresearch/runs/" in path.as_posix():
            continue
        validate_markdown_links(path)

    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        scan_for_forbidden_strings(path)

    if errors:
        print("validation failed:", file=sys.stderr)
        for message in errors:
            print(f"- {message}", file=sys.stderr)
        return 1

    print("validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
