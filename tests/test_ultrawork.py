from __future__ import annotations

import io
import json
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from teaagent import UltraworkStore
from teaagent.cli import main


def _sleep_command(seconds: float) -> list[str]:
    return [sys.executable, "-c", f"import time; time.sleep({seconds})"]


class UltraworkStoreTests(unittest.TestCase):
    def test_start_returns_record_and_persists_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = UltraworkStore(tmp)

            record = store.start(_sleep_command(0.5), label="demo")

            self.assertEqual(len(record.command), 3)
            self.assertEqual(record.label, "demo")
            self.assertTrue(Path(record.log_path).exists())
            persisted = json.loads((Path(tmp) / ".teaagent" / "ultrawork" / f"{record.worker_id}.json").read_text())
            self.assertEqual(persisted["pid"], record.pid)

            store.stop(record.worker_id)

    def test_list_marks_alive_then_dead(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = UltraworkStore(tmp)
            record = store.start(_sleep_command(0.2))

            alive = store.list()
            self.assertTrue(alive[0]["alive"])

            time.sleep(0.4)

            dead = store.list()
            self.assertFalse(dead[0]["alive"])
            self.assertEqual(dead[0]["worker_id"], record.worker_id)

    def test_stop_terminates_running_worker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = UltraworkStore(tmp)
            record = store.start(_sleep_command(5.0))

            stopped = store.stop(record.worker_id, timeout_seconds=1.0)

            self.assertFalse(stopped["alive"])
            self.assertIn(stopped["stop_signal"], {"SIGTERM", "SIGKILL"})
            self.assertFalse(UltraworkStore._is_alive(record.pid))

    def test_show_unknown_worker_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(FileNotFoundError):
            UltraworkStore(tmp).show("missing")

    def test_cli_ultrawork_list_returns_persisted_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = UltraworkStore(tmp)
            record = store.start(_sleep_command(0.2))

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["ultrawork", "list", "--root", tmp])

            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload[0]["worker_id"], record.worker_id)

            store.stop(record.worker_id)

    def test_cli_ultrawork_stop_marks_record_stopped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = UltraworkStore(tmp)
            record = store.start(_sleep_command(2.0))

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["ultrawork", "stop", record.worker_id, "--root", tmp])

            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertFalse(payload["alive"])


if __name__ == "__main__":
    unittest.main()
