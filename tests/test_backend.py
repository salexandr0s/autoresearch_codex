from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from autoresearch.backend import run_codex


class BackendTests(unittest.TestCase):
    def test_run_codex_uses_unattended_workspace_write_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            final_file = temp / "final.md"
            events_file = temp / "events.jsonl"
            args_file = temp / "args.json"
            fake_codex = temp / "fake-codex"
            fake_codex.write_text(
                "#!/usr/bin/env python3\n"
                "import json\n"
                "import sys\n"
                "from pathlib import Path\n"
                "Path(sys.argv[sys.argv.index('-o') + 1]).write_text('OK\\n', encoding='utf-8')\n"
                f"Path({str(args_file)!r}).write_text(json.dumps(sys.argv[1:]), encoding='utf-8')\n"
                "print('{\"ok\": true}')\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)

            result = run_codex(
                codex_bin=str(fake_codex),
                cwd=temp,
                prompt="Return OK",
                final_message_file=final_file,
                agent_jsonl_file=events_file,
            )

            argv = json.loads(args_file.read_text(encoding="utf-8"))
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.final_message.strip(), "OK")
            self.assertEqual(argv[:5], ["-a", "never", "-s", "workspace-write", "exec"])

    def test_run_codex_can_use_read_only_sandbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            final_file = temp / "final.md"
            events_file = temp / "events.jsonl"
            args_file = temp / "args.json"
            fake_codex = temp / "fake-codex"
            fake_codex.write_text(
                "#!/usr/bin/env python3\n"
                "import json\n"
                "import sys\n"
                "from pathlib import Path\n"
                "Path(sys.argv[sys.argv.index('-o') + 1]).write_text('OK\\n', encoding='utf-8')\n"
                f"Path({str(args_file)!r}).write_text(json.dumps(sys.argv[1:]), encoding='utf-8')\n"
                "print('{\"ok\": true}')\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)

            run_codex(
                codex_bin=str(fake_codex),
                cwd=temp,
                prompt="Return OK",
                final_message_file=final_file,
                agent_jsonl_file=events_file,
                sandbox_mode="read-only",
            )

            argv = json.loads(args_file.read_text(encoding="utf-8"))
            self.assertEqual(argv[:5], ["-a", "never", "-s", "read-only", "exec"])

    def test_run_codex_accepts_skip_git_and_schema_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            final_file = temp / "final.json"
            events_file = temp / "events.jsonl"
            args_file = temp / "args.json"
            schema_file = temp / "schema.json"
            schema_file.write_text("{}", encoding="utf-8")
            fake_codex = temp / "fake-codex"
            fake_codex.write_text(
                "#!/usr/bin/env python3\n"
                "import json\n"
                "import sys\n"
                "from pathlib import Path\n"
                "Path(sys.argv[sys.argv.index('-o') + 1]).write_text('{\"ok\": true}\\n', encoding='utf-8')\n"
                f"Path({str(args_file)!r}).write_text(json.dumps(sys.argv[1:]), encoding='utf-8')\n"
                "print('{\"ok\": true}')\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)

            run_codex(
                codex_bin=str(fake_codex),
                cwd=temp,
                prompt="Return JSON",
                final_message_file=final_file,
                agent_jsonl_file=events_file,
                skip_git_repo_check=True,
                output_schema_file=schema_file,
                deadline_seconds=5,
            )

            argv = json.loads(args_file.read_text(encoding="utf-8"))
            self.assertIn("--skip-git-repo-check", argv)
            self.assertIn("--output-schema", argv)


if __name__ == "__main__":
    unittest.main()
