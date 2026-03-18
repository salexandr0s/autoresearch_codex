from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"


def write_fake_codex(bin_path: Path, queue_path: Path) -> None:
    script = (
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import os\n"
        "import time\n"
        "import sys\n"
        "from pathlib import Path\n\n"
        "args = sys.argv[1:]\n"
        "if '--version' in args:\n"
        "    print('codex-fake 0.1')\n"
        "    raise SystemExit(0)\n\n"
        "cwd = Path(args[args.index('-C') + 1]) if '-C' in args else Path.cwd()\n"
        "out_file = Path(args[args.index('-o') + 1]) if '-o' in args else cwd / 'codex-final.md'\n"
        "queue_path = Path(os.environ['FAKE_CODEX_QUEUE'])\n"
        "payload = json.loads(queue_path.read_text(encoding='utf-8'))\n"
        "if not payload['calls']:\n"
        "    out_file.write_text('Hypothesis: none\\nSummary: no queued response\\n', encoding='utf-8')\n"
        "    raise SystemExit(1)\n"
        "call = payload['calls'].pop(0)\n"
        "queue_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')\n"
        "time.sleep(call.get('sleep_seconds', 0))\n"
        "for item in call.get('writes', []):\n"
        "    target = cwd / item['path']\n"
        "    target.parent.mkdir(parents=True, exist_ok=True)\n"
        "    target.write_text(item['content'], encoding='utf-8')\n"
        "out_file.write_text(call.get('final', 'Hypothesis: fake\\nSummary: fake\\n'), encoding='utf-8')\n"
        "print(json.dumps({'ok': True}))\n"
        "raise SystemExit(call.get('exit_code', 0))\n"
    )
    bin_path.write_text(script, encoding="utf-8")
    bin_path.chmod(0o755)
    queue_path.write_text(json.dumps({"calls": []}, indent=2), encoding="utf-8")


class RuntimeIntegrationTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="autoresearch-tests-")
        self.repo = Path(self.temp_dir.name) / "repo"
        self.repo.mkdir(parents=True, exist_ok=True)
        self._copy_scaffold()
        self.fake_codex = Path(self.temp_dir.name) / "fake-codex"
        self.queue_path = Path(self.temp_dir.name) / "fake-codex-queue.json"
        write_fake_codex(self.fake_codex, self.queue_path)
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(SRC_PATH)
        self.env["AUTORESEARCH_CODEX_BIN"] = str(self.fake_codex)
        self.env["FAKE_CODEX_QUEUE"] = str(self.queue_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _copy_scaffold(self) -> None:
        shutil.copy2(REPO_ROOT / "AGENTS.md", self.repo / "AGENTS.md")
        shutil.copytree(REPO_ROOT / ".agents", self.repo / ".agents")
        shutil.copytree(REPO_ROOT / ".codex", self.repo / ".codex")
        (self.repo / ".autoresearch" / "targets").mkdir(parents=True, exist_ok=True)
        (self.repo / ".autoresearch" / "runs").mkdir(parents=True, exist_ok=True)
        shutil.copytree(REPO_ROOT / "codex", self.repo / "codex")
        (self.repo / "scripts").mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / "scripts" / "validate-codex-assets.py", self.repo / "scripts" / "validate-codex-assets.py")

    def _init_git(self) -> None:
        self._run("git init -b main")
        self._run('git config user.name "Test User"')
        self._run('git config user.email "test@example.com"')

    def _commit_all(self, message: str) -> None:
        self._run("git add -A")
        self._run(f'git commit -m "{message}"')

    def _run(self, command: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["/bin/zsh", "-lc", command], cwd=str(cwd or self.repo), text=True, capture_output=True, check=True)

    def _cli(self, *args: str, expect_ok: bool = True) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(
            [sys.executable, "-m", "autoresearch.cli", *args],
            cwd=str(self.repo),
            text=True,
            capture_output=True,
            env=self.env,
        )
        if expect_ok and proc.returncode != 0:
            self.fail(f"CLI failed: {' '.join(args)}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
        return proc

    def _set_queue(self, calls: list[dict]) -> None:
        self.queue_path.write_text(json.dumps({"calls": calls}, indent=2), encoding="utf-8")

    def test_plan_generates_target(self) -> None:
        self._init_git()
        (self.repo / "README.md").write_text("fixture\n", encoding="utf-8")
        self._commit_all("baseline")
        self._set_queue([
            {
                "final": textwrap.dedent(
                    """
                    {
                      "name": "generated",
                      "goal": "Improve the fixture",
                      "scope": {
                        "include": ["src/**"],
                        "exclude": []
                      },
                      "metric": {
                        "name": "score",
                        "direction": "higher",
                        "extractor": {
                          "type": "regex",
                          "value": "score: ([0-9.]+)"
                        }
                      },
                      "verify": {
                        "command": "python3 score.py"
                      },
                      "guard": {
                        "command": "python3 -m py_compile score.py"
                      },
                      "stopping": {
                        "max_iterations": 3,
                        "goal_threshold": 3,
                        "stagnation_reflect_after": 2,
                        "stop_after_consecutive_failures": 3
                      }
                    }
                    """
                ).strip()
            }
        ])
        proc = self._cli("plan", "--goal", "Improve the fixture", "--target-name", "generated")
        target_path = Path(proc.stdout.strip())
        self.assertTrue(target_path.exists())
        self.assertIn("metric:", target_path.read_text(encoding="utf-8"))

    def test_plan_timeout_uses_fallback_target(self) -> None:
        self._init_git()
        (self.repo / "tests").mkdir(parents=True, exist_ok=True)
        (self.repo / "tests" / "test_sample.py").write_text(
            "import unittest\n\nclass SampleTests(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        self._commit_all("baseline")
        self._set_queue([{"sleep_seconds": 2, "final": "{}"}])
        proc = self._cli("plan", "--goal", "Increase regression coverage", "--target-name", "fallback", "--deadline-seconds", "1")
        target_path = Path(proc.stdout.strip())
        self.assertTrue(target_path.exists())
        text = target_path.read_text(encoding="utf-8")
        self.assertIn("test_count", text)
        run_dir = sorted((self.repo / ".autoresearch" / "runs").iterdir())[-1]
        summary = (run_dir / "summary.md").read_text(encoding="utf-8")
        self.assertIn("completion mode: fallback", summary)

    def test_scaffold_validator_passes_in_target_repo_mode(self) -> None:
        self._init_git()
        (self.repo / "README.md").write_text("fixture\n", encoding="utf-8")
        self._commit_all("baseline")
        proc = self._run("python3 scripts/validate-codex-assets.py")
        self.assertIn("validation passed", proc.stdout)

    def test_loop_keeps_improvement_and_discards_regression(self) -> None:
        self._init_git()
        (self.repo / "app.txt").write_text("score=1\n", encoding="utf-8")
        (self.repo / "score.py").write_text(
            "from pathlib import Path\ntext = Path('app.txt').read_text().strip().split('=')[1]\nprint(f'score: {text}')\n",
            encoding="utf-8",
        )
        (self.repo / ".autoresearch" / "targets" / "default.yaml").write_text(
            textwrap.dedent(
                """
                name: fixture
                goal: Raise the score in app.txt
                scope:
                  include:
                    - app.txt
                  exclude: []
                metric:
                  name: score
                  direction: higher
                  extractor:
                    type: regex
                    value: 'score: ([0-9.]+)'
                verify:
                  command: python3 score.py
                guard:
                  command: python3 -m py_compile score.py
                stopping:
                  max_iterations: 2
                  goal_threshold: null
                  stagnation_reflect_after: 1
                  stop_after_consecutive_failures: 3
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        self._commit_all("baseline")
        self._set_queue([
            {
                "writes": [{"path": "app.txt", "content": "score=2\n"}],
                "final": "Hypothesis: increase the score\nSummary: set the score to 2\n",
            },
            {
                "writes": [{"path": "app.txt", "content": "score=1\n"}],
                "final": "Hypothesis: lower the score\nSummary: revert to 1\n",
            },
        ])
        proc = self._cli("loop", "--max-iterations", "2")
        run_dir = Path(proc.stdout.strip())
        results = (run_dir / "results.tsv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(results), 4)
        self.assertIn("\tkeep\t", results[2])
        self.assertIn("\tdiscard\t", results[3])
        summary = (run_dir / "summary.md").read_text(encoding="utf-8")
        self.assertIn("best metric: 2.000000", summary)

    def test_fix_uses_findings_context(self) -> None:
        self._init_git()
        (self.repo / "app.txt").write_text("score=1\n", encoding="utf-8")
        (self.repo / "score.py").write_text(
            "from pathlib import Path\ntext = Path('app.txt').read_text().strip().split('=')[1]\nprint(f'score: {text}')\n",
            encoding="utf-8",
        )
        findings = self.repo / ".autoresearch" / "runs" / "debug-run" / "artifacts"
        findings.mkdir(parents=True, exist_ok=True)
        (findings / "findings.md").write_text("Parser bug found\n", encoding="utf-8")
        (self.repo / ".autoresearch" / "targets" / "default.yaml").write_text(
            textwrap.dedent(
                """
                name: fix-fixture
                goal: Lower the numeric error count in app.txt
                scope:
                  include:
                    - app.txt
                  exclude: []
                metric:
                  name: score
                  direction: lower
                  extractor:
                    type: regex
                    value: 'score: ([0-9.]+)'
                verify:
                  command: python3 score.py
                stopping:
                  max_iterations: 1
                  goal_threshold: null
                  stagnation_reflect_after: 1
                  stop_after_consecutive_failures: 2
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        self._commit_all("baseline")
        self._set_queue([
            {
                "writes": [{"path": "app.txt", "content": "score=0\n"}],
                "final": "Hypothesis: reduce the error count\nSummary: set score to 0\n",
            }
        ])
        proc = self._cli("fix", "--max-iterations", "1")
        run_dir = Path(proc.stdout.strip())
        summary = (run_dir / "summary.md").read_text(encoding="utf-8")
        self.assertIn("best metric: 0.000000", summary)

    def test_debug_security_and_ship_create_artifacts(self) -> None:
        self._init_git()
        (self.repo / "README.md").write_text("fixture\n", encoding="utf-8")
        self._commit_all("baseline")

        for command, artifact in [
            ("debug", "findings.md"),
            ("security", "security-report.md"),
            ("ship", "ship-checklist.md"),
        ]:
            with self.subTest(command=command):
                self._set_queue([
                    {
                        "final": json.dumps(
                            {
                                "title": "ship report",
                                "summary": "generated ship artifact",
                                "checklist_markdown": "# ship\n\ngenerated ship artifact\n",
                                "release_plan_markdown": "generated ship release plan\n",
                            }
                            if command == "ship"
                            else {
                                "title": f"{command} report",
                                "summary": f"generated {command} artifact",
                                "findings": [],
                                "artifact_markdown": f"# {command}\n\ngenerated {command} artifact\n",
                            }
                        )
                    }
                ])
                args = [command]
                if command == "debug":
                    args += ["--summary", "Investigate the fixture"]
                proc = self._cli(*args)
                run_dir = Path(proc.stdout.strip())
                self.assertTrue((run_dir / "artifacts" / artifact).exists())

    def test_debug_timeout_uses_structured_fallback(self) -> None:
        self._init_git()
        (self.repo / "README.md").write_text("fixture\n", encoding="utf-8")
        self._commit_all("baseline")
        self._set_queue([{"sleep_seconds": 2, "final": "{}"}])
        proc = self._cli("debug", "--summary", "Investigate the fixture", "--deadline-seconds", "1")
        run_dir = Path(proc.stdout.strip())
        summary = (run_dir / "summary.md").read_text(encoding="utf-8")
        artifact = (run_dir / "artifacts" / "findings.md").read_text(encoding="utf-8")
        self.assertIn("completion mode: fallback", summary)
        self.assertIn("fallback", artifact.lower())

    def test_ship_execute_stays_dry_run_only(self) -> None:
        self._init_git()
        (self.repo / "README.md").write_text("fixture\n", encoding="utf-8")
        self._commit_all("baseline")
        self._set_queue([
            {
                "final": json.dumps(
                    {
                        "title": "ship report",
                        "summary": "generated ship checklist only",
                        "checklist_markdown": "# ship\n\ngenerated ship checklist only\n",
                        "release_plan_markdown": "generated ship checklist only\n",
                    }
                )
            }
        ])

        proc = self._cli("ship", "--summary", "Deploy the fixture", "--execute")

        run_dir = Path(proc.stdout.strip())
        self.assertTrue((run_dir / "artifacts" / "ship-checklist.md").exists())
        release_plan = (run_dir / "artifacts" / "release-plan.md").read_text(encoding="utf-8")
        self.assertIn("Deploy the fixture", release_plan)
        self.assertIn("Execution was requested, but the runner must not perform unattended push/publish/deploy/merge/send actions.", release_plan)
        self.assertIn("Produce a dry-run plan only.", release_plan)


if __name__ == "__main__":
    unittest.main()
