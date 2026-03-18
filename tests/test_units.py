from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autoresearch.context import build_context_workspace, infer_fallback_target
from autoresearch.metrics import extract_metric
from autoresearch.models import MetricExtractor
from autoresearch.prompts import build_plan_prompt
from autoresearch.targets import parse_target


class TargetAndMetricTests(unittest.TestCase):
    def test_parse_target_accepts_valid_config(self) -> None:
        target = parse_target(
            {
                "name": "demo",
                "goal": "improve demo",
                "scope": {"include": ["src/**"], "exclude": []},
                "metric": {
                    "name": "score",
                    "direction": "higher",
                    "extractor": {"type": "regex", "value": r"score: ([0-9.]+)"},
                },
                "verify": {"command": "python3 score.py"},
                "stopping": {
                    "max_iterations": 3,
                    "goal_threshold": None,
                    "stagnation_reflect_after": 2,
                    "stop_after_consecutive_failures": 3,
                },
            }
        )
        self.assertEqual(target.metric.direction, "higher")
        self.assertEqual(target.scope.include, ["src/**"])

    def test_regex_metric_extractor(self) -> None:
        value = extract_metric(MetricExtractor("regex", r"score: ([0-9.]+)"), "score: 2.5\n", Path.cwd(), Path("verify.log"))
        self.assertEqual(value, 2.5)

    def test_script_metric_extractor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            log_path = temp / "verify.log"
            log_path.write_text("score: 4\n", encoding="utf-8")
            script = temp / "extract.py"
            script.write_text(
                "#!/usr/bin/env python3\nfrom pathlib import Path\nprint(Path(__import__('sys').argv[1]).read_text().split(':')[1].strip())\n",
                encoding="utf-8",
            )
            script.chmod(0o755)
            value = extract_metric(MetricExtractor("script", str(script)), log_path.read_text(encoding="utf-8"), temp, log_path)
            self.assertEqual(value, 4.0)

    def test_context_workspace_and_prompt_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "repo"
            repo.mkdir(parents=True, exist_ok=True)
            (repo / "README.md").write_text("fixture\n", encoding="utf-8")
            (repo / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
            (repo / "tests").mkdir(parents=True, exist_ok=True)
            (repo / "tests" / "test_sample.py").write_text("import unittest\n", encoding="utf-8")
            run_root = repo / ".autoresearch" / "runs" / "test"
            artifacts = run_root / "artifacts"
            context_workspace = run_root / "context"
            artifacts.mkdir(parents=True, exist_ok=True)
            packet = build_context_workspace(
                repo_root=repo,
                workspace=context_workspace,
                artifacts_dir=artifacts,
                workflow="plan",
                request_text="Increase regression coverage for tests",
            )
            prompt = build_plan_prompt(
                target_name="demo",
                goal="Increase regression coverage",
                context="",
                constraints="",
                done_when="",
                context_summary=packet.summary_text,
            )
            self.assertLess(len(prompt.encode("utf-8")), 8_000)
            self.assertNotIn("AGENTS.md", prompt)
            self.assertTrue((artifacts / "context-summary.md").exists())

    def test_plan_fallback_target_infers_test_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "repo"
            repo.mkdir(parents=True, exist_ok=True)
            (repo / "tests").mkdir(parents=True, exist_ok=True)
            (repo / "tests" / "test_sample.py").write_text(
                "import unittest\n\nclass SampleTests(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            run_root = repo / ".autoresearch" / "runs" / "test"
            artifacts = run_root / "artifacts"
            context_workspace = run_root / "context"
            artifacts.mkdir(parents=True, exist_ok=True)
            packet = build_context_workspace(
                repo_root=repo,
                workspace=context_workspace,
                artifacts_dir=artifacts,
                workflow="plan",
                request_text="Increase regression coverage",
            )
            target = infer_fallback_target(
                target_name="demo",
                goal="Increase regression coverage",
                constraints="",
                context_packet=packet,
            )
            self.assertIsNotNone(target)
            assert target is not None
            self.assertEqual(target.metric.name, "test_count")
            self.assertEqual(target.metric.direction, "higher")
            self.assertIn("unittest", target.verify.command)

    def test_ship_context_excludes_skills_and_test_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "repo"
            repo.mkdir(parents=True, exist_ok=True)
            (repo / "README.md").write_text("fixture\n", encoding="utf-8")
            (repo / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
            (repo / "scripts").mkdir(parents=True, exist_ok=True)
            (repo / "scripts" / "release.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            (repo / "docs" / "maintainers").mkdir(parents=True, exist_ok=True)
            (repo / "docs" / "maintainers" / "release.md").write_text("release\n", encoding="utf-8")
            (repo / "docs" / "maintainers" / "smoke.md").write_text("smoke\n", encoding="utf-8")
            (repo / ".agents" / "skills" / "ship").mkdir(parents=True, exist_ok=True)
            (repo / ".agents" / "skills" / "ship" / "SKILL.md").write_text("skill\n", encoding="utf-8")
            (repo / "test-fixtures" / "sample").mkdir(parents=True, exist_ok=True)
            (repo / "test-fixtures" / "sample" / "README.md").write_text("fixture sample\n", encoding="utf-8")
            run_root = repo / ".autoresearch" / "runs" / "ship"
            artifacts = run_root / "artifacts"
            context_workspace = run_root / "context"
            artifacts.mkdir(parents=True, exist_ok=True)
            packet = build_context_workspace(
                repo_root=repo,
                workspace=context_workspace,
                artifacts_dir=artifacts,
                workflow="ship",
                request_text="Prepare a release-readiness checklist",
            )
            selected = {item.source_path for item in packet.selected_files}
            self.assertNotIn(".agents/skills/ship/SKILL.md", selected)
            self.assertFalse(any(path.startswith("test-fixtures/") for path in selected))


if __name__ == "__main__":
    unittest.main()
