from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autoresearch.metrics import extract_metric
from autoresearch.models import MetricExtractor
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


if __name__ == "__main__":
    unittest.main()
