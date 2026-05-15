"""AC-NEW-20: End-to-end code-change repair loop.

As a user, I want the agent to run a failing test, apply a scoped fix, rerun
the test, inspect the diff, and summarize the result.

Acceptance criteria:
- Baseline test fails before the agent run.
- Agent run performs read/edit/test/diff/final sequence and completes.
- Post-run test passes and edited code contains the fix.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

from conftest import FakeAdapter

from teaagent.cli import main


def test_agent_fixes_failing_test_and_reports_diff_summary() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        calc = root / "calc.py"
        test_file = root / "test_calc.py"
        calc.write_text(
            "def add(a: int, b: int) -> int:\n    return a - b\n", encoding="utf-8"
        )
        test_file.write_text(
            "from calc import add\n\n\ndef test_add() -> None:\n    assert add(1, 2) == 3\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "init"], cwd=tmp, check=True, capture_output=True)

        baseline = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=tmp,
            text=True,
            capture_output=True,
        )
        assert baseline.returncode != 0

        adapter = FakeAdapter(
            [
                json.dumps(
                    {
                        "type": "tool",
                        "tool_name": "workspace_run_shell_mutate",
                        "arguments": {
                            "command": f"{sys.executable} -m pytest -q",
                            "timeout_seconds": 10,
                        },
                        "call_id": "test-before",
                    }
                ),
                '{"type":"tool","tool_name":"workspace_read_file_hashed","arguments":{"path":"calc.py"},"call_id":"read-calc"}',
                json.dumps(
                    {
                        "type": "tool",
                        "tool_name": "workspace_write_file",
                        "arguments": {
                            "path": "calc.py",
                            "content": (
                                "def add(a: int, b: int) -> int:\n"
                                "    return a + b  # fixed by agent\n"
                            ),
                        },
                        "call_id": "fix-calc",
                    }
                ),
                json.dumps(
                    {
                        "type": "tool",
                        "tool_name": "workspace_run_shell_mutate",
                        "arguments": {
                            "command": f"{sys.executable} -m pytest -q",
                            "timeout_seconds": 10,
                        },
                        "call_id": "test-after",
                    }
                ),
                '{"type":"tool","tool_name":"workspace_run_shell_inspect","arguments":{"command":"git diff -- calc.py","timeout_seconds":5},"call_id":"diff-calc"}',
                '{"type":"final","content":"Pytest rerun passed; calc.py updated to use addition; diff reviewed."}',
            ]
        )

        run_output = io.StringIO()
        with redirect_stdout(run_output):
            exit_code = main(
                [
                    "agent",
                    "run",
                    "gpt",
                    "Fix the failing test and summarize the patch",
                    "--root",
                    tmp,
                    "--allow-destructive",
                ],
                _adapter_factory=lambda _provider, model=None: adapter,
            )
        run_payload = json.loads(run_output.getvalue())

        assert exit_code == 0
        assert run_payload["status"] == "completed"
        assert run_payload["run_mode"] == "execution"
        assert run_payload["final_answer"] is not None
        assert "Pytest rerun passed" in run_payload["final_answer"]
        assert run_payload["audit_summary"]["destructive_tool_calls"] == 3
        assert run_payload["audit_summary"]["tool_names"] == [
            "workspace_run_shell_mutate",
            "workspace_read_file_hashed",
            "workspace_write_file",
            "workspace_run_shell_inspect",
        ]
        assert "return a + b" in calc.read_text(encoding="utf-8")

        verify = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=tmp,
            text=True,
            capture_output=True,
        )
        assert verify.returncode == 0
