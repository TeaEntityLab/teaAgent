# test-type: behavior
"""Audit logging must not import OpenTelemetry until export is enabled."""

from __future__ import annotations

import subprocess
import sys


def test_importing_audit_does_not_load_opentelemetry() -> None:
    """A hook or CLI that only appends a log must not start the OTel SDK."""
    probe = (
        'import sys\n'
        'import teaagent.audit\n'
        'loaded = [\n'
        '    name for name in sys.modules\n'
        '    if name == "teaagent.telemetry" or name.startswith("opentelemetry")\n'
        ']\n'
        'raise SystemExit(0 if not loaded else "loaded " + ",".join(loaded))\n'
    )
    proc = subprocess.run(
        [sys.executable, '-c', probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_enable_opentelemetry_still_registers_a_sink() -> None:
    """The export path still attaches a sink after the import moved inside it."""
    probe = (
        'from teaagent.audit import AuditLogger\n'
        'logger = AuditLogger(path=None)\n'
        'logger.enable_opentelemetry(service_name="teaagent-import-test")\n'
        'print(len(logger._sinks))\n'
    )
    proc = subprocess.run(
        [sys.executable, '-c', probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == '1'
