from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autoresearch.context import build_context_workspace, infer_fallback_target
from autoresearch.metrics import extract_metric
from autoresearch.models import MetricExtractor
from autoresearch.platform import PlatformReport, platform_warning_messages, target_platform_warning_messages
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

    def test_plan_fallback_target_infers_val_bpb_for_karpathy_style_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "repo"
            repo.mkdir(parents=True, exist_ok=True)
            (repo / "README.md").write_text("Karpathy-style fixture\nmetric: val_bpb\n", encoding="utf-8")
            (repo / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
            (repo / "program.md").write_text("Each experiment edits train.py and optimizes val_bpb.\n", encoding="utf-8")
            (repo / "prepare.py").write_text("print('prepare')\n", encoding="utf-8")
            (repo / "train.py").write_text("print('val_bpb: 1.234567')\nprint('peak_vram_mb: 0')\n", encoding="utf-8")
            run_root = repo / ".autoresearch" / "runs" / "test"
            artifacts = run_root / "artifacts"
            context_workspace = run_root / "context"
            artifacts.mkdir(parents=True, exist_ok=True)
            packet = build_context_workspace(
                repo_root=repo,
                workspace=context_workspace,
                artifacts_dir=artifacts,
                workflow="plan",
                request_text="Improve the training loop for this autoresearch-style repo",
            )
            target = infer_fallback_target(
                target_name="train-loop",
                goal="Improve the training loop for this autoresearch-style repo",
                constraints="",
                context_packet=packet,
            )
            self.assertIsNotNone(target)
            assert target is not None
            self.assertEqual(target.metric.name, "val_bpb")
            self.assertEqual(target.metric.direction, "lower")
            self.assertEqual(target.verify.command, "uv run train.py")
            self.assertEqual(target.scope.include, ["train.py"])

    def test_platform_warning_messages_for_macos_edge_cases(self) -> None:
        report = PlatformReport(
            os_name="darwin",
            arch="x86_64",
            is_macos=True,
            is_apple_silicon=False,
            python_version="3.11.9",
            git_available=True,
            uv_available=True,
            codex_available=True,
            caffeinate_available=False,
            xcode_clt_available=False,
            torch_importable=True,
            torch_version="2.6.0",
            mps_available=False,
            cuda_available=False,
        )
        warnings = platform_warning_messages(report)
        self.assertTrue(any("Intel Mac" in item for item in warnings))
        self.assertTrue(any("caffeinate" in item for item in warnings))
        self.assertTrue(any("Xcode Command Line Tools" in item for item in warnings))

    def test_target_platform_warning_messages_for_peak_vram_on_macos(self) -> None:
        report = PlatformReport(
            os_name="darwin",
            arch="arm64",
            is_macos=True,
            is_apple_silicon=True,
            python_version="3.11.9",
            git_available=True,
            uv_available=True,
            codex_available=True,
            caffeinate_available=True,
            xcode_clt_available=True,
            torch_importable=True,
            torch_version="2.6.0",
            mps_available=True,
            cuda_available=False,
        )
        target = parse_target(
            {
                "name": "mac-vram",
                "goal": "Lower peak_vram_mb on a CUDA-style target",
                "scope": {"include": ["train.py"], "exclude": []},
                "metric": {
                    "name": "peak_vram_mb",
                    "direction": "lower",
                    "extractor": {"type": "regex", "value": r"peak_vram_mb:\s*([0-9.]+)"},
                },
                "verify": {"command": "python3 train.py --cuda"},
                "stopping": {
                    "max_iterations": 3,
                    "goal_threshold": None,
                    "stagnation_reflect_after": 2,
                    "stop_after_consecutive_failures": 3,
                },
            }
        )
        warnings = target_platform_warning_messages(report, target)
        self.assertTrue(any("CUDA/NVIDIA" in item for item in warnings))
        self.assertTrue(any("peak_vram_mb" in item for item in warnings))

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
