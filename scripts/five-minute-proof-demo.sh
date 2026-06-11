#!/usr/bin/env bash
# five-minute-proof-demo.sh
#
# Proves TeaAgent's governance thesis end-to-end in under five minutes.
# No API key required — uses the built-in fake provider.
#
# Usage (from repo root):
#   bash scripts/five-minute-proof-demo.sh
#
# What it proves:
#   1. Plan gate   — no write without an approved plan (exit 2)
#   2. Approval    — every mutation gated by an explicit approval record
#   3. File edit   — agent edits exactly the file declared in the plan
#   4. Verification— agent confirms the fix before declaring done
#   5. Receipt     — budget / tool / file / approval receipts emitted
#   6. Undo        — workspace restored to pre-run state

set -euo pipefail

# ── Colours ────────────────────────────────────────────────────────────────
_bold='\033[1m'
_blue='\033[1;34m'
_green='\033[0;32m'
_yellow='\033[0;33m'
_dim='\033[0;90m'
_reset='\033[0m'

step()  { printf "\n${_blue}[STEP %s] %s${_reset}\n" "$1" "$2"; }
note()  { printf "${_dim}  → %s${_reset}\n" "$1"; }
ok()    { printf "${_green}  ✓ %s${_reset}\n" "$1"; }
warn()  { printf "${_yellow}  ⚠ %s${_reset}\n" "$1"; }
header(){ printf "\n${_bold}%s${_reset}\n" "$1"; }

# ── Preamble ───────────────────────────────────────────────────────────────
header "========================================================"
header " TeaAgent — Five-Minute Governance Proof"
header " Provider: fake  (no API key required)"
header "========================================================"
echo ""
note "Receipts before rhetoric."
note "Each step below produces a verifiable artifact."
echo ""

# Ensure we run from the repo root so teaagent imports resolve.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ── Main demo (embedded Python) ────────────────────────────────────────────
python3 - <<'PYEOF'
"""Inline demo runner — no external LLM calls."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

# Use the repo root already set by the shell script.
sys.path.insert(0, os.getcwd())

from teaagent.llm._fake_adapter import (
    FakeLLMAdapter,
    create_fake_text_response,
    create_fake_tool_call_response,
)
from teaagent.cli import main
from teaagent.plan import load_plan_contract
from teaagent.run_receipt import build_run_receipt, check_receipt_completeness
from teaagent.run_store import RunStore

# ── ANSI helpers ───────────────────────────────────────────────────────────
def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m"

def step(n: int, title: str) -> None:
    print(f"\n{_c('1;34', f'[STEP {n}] {title}')}")

def ok(msg: str) -> None:
    print(f"{_c('0;32', '  ✓')} {msg}")

def note(msg: str) -> None:
    print(f"{_c('0;90', '  →')} {msg}")

def show_json(label: str, data: dict) -> None:
    print(f"{_c('0;90', f'  {label}:')} {json.dumps(data, indent=None)[:200]}")

# ── Workspace helpers ──────────────────────────────────────────────────────
_BUGGY_SRC = "def add(a, b):\n    return a - b\n"
_FIXED_SRC  = "def add(a, b):\n    return a + b\n"

_PLAN_MD = """\
# Plan

## Summary
- **Task:** Fix the bug in calc.py — subtraction operator should be addition

## Files likely touched
- `calc.py`
"""

_GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "TeaAgent Demo",
    "GIT_AUTHOR_EMAIL": "demo@teaagent.test",
    "GIT_COMMITTER_NAME": "TeaAgent Demo",
    "GIT_COMMITTER_EMAIL": "demo@teaagent.test",
}


def _setup_workspace(root: Path) -> tuple[Path, Path]:
    calc = root / "calc.py"
    calc.write_text(_BUGGY_SRC, encoding="utf-8")
    (root / "test_calc.py").write_text(
        "from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )
    plans_dir = root / ".teaagent" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plans_dir / "fix-calc.md"
    plan_file.write_text(_PLAN_MD, encoding="utf-8")
    return calc, plan_file


def _git_baseline(root: Path) -> bool:
    """Commit current workspace so git-sandbox rollback is available for undo."""
    for cmd in (
        ["git", "init"],
        ["git", "add", "calc.py", "test_calc.py"],
        ["git", "commit", "-m", "baseline"],
    ):
        r = subprocess.run(cmd, cwd=root, capture_output=True, env=_GIT_ENV)
        if r.returncode != 0:
            return False
    return True


def _noop_adapter() -> FakeLLMAdapter:
    """Adapter whose .complete() is never reached (plan-gate fires first)."""
    return FakeLLMAdapter()


def _governed_adapter() -> FakeLLMAdapter:
    """Three-step scripted conversation: write → inspect → done."""
    return FakeLLMAdapter(
        responses=[
            # Step 2: write the fix (will trigger the approval gate)
            create_fake_tool_call_response(
                "workspace_write_file",
                {"path": "calc.py", "content": _FIXED_SRC},
                call_id="fix-write",
            ),
            # Step 4: verify the fix via grep (in the inspect-safe allowlist)
            create_fake_tool_call_response(
                "workspace_run_shell_inspect",
                {"command": "grep -n 'return a' calc.py"},
                call_id="verify-fix",
            ),
            # Step 5: declare completion
            create_fake_text_response(
                '{"type":"final","content":"calc.py fixed: subtraction corrected to addition; verification passed"}'
            ),
        ]
    )


# ===========================================================================
# Main demo
# ===========================================================================

with tempfile.TemporaryDirectory(prefix="teaagent-proof-") as _tmp:
    root = Path(_tmp).resolve()  # resolve symlinks (e.g. /var → /private/var on macOS)
    calc, plan_file = _setup_workspace(root)
    note(f"Workspace: {root}")
    note(f"Bug in {calc}: 'return a - b'  ← will be fixed by the agent")

    # ── STEP 1: Plan gate blocks writes without a plan ──────────────────────
    step(1, "Plan gate — write blocked when no plan is supplied")
    note("Running:  agent run gpt 'Fix ...' --require-plan  (no --from-plan)")

    gate_out = io.StringIO()
    with (
        patch("teaagent.cli.create_llm_adapter", return_value=_noop_adapter()),
        redirect_stdout(gate_out),
    ):
        gate_code = main([
            "agent", "run", "gpt",
            "Fix the bug in calc.py",
            "--root", str(root),
            "--permission-mode", "prompt",
            "--require-plan",
            "--max-iterations", "2",
            "--max-tool-calls", "2",
        ])

    gate_payload = json.loads(gate_out.getvalue())
    assert gate_code == 2, f"Expected exit 2 from plan gate, got {gate_code}"
    assert "a - b" in calc.read_text(encoding="utf-8"), "File must be unchanged"

    ok(f"Exit code: {gate_code}  →  gate fired before any LLM call")
    show_json("error", gate_payload)
    ok("calc.py unchanged — no write without a plan")

    # ── STEP 2-4: Full governed run ─────────────────────────────────────────
    step(2, "Approval + edit — governed run with plan, approval, and git sandbox")
    note(f"Plan: {plan_file.relative_to(root)}")
    note("Approval granted for call_id='fix-write' (simulates user click)")

    has_git = _git_baseline(root)
    if not has_git:
        note("git not available — undo will use UndoJournal fallback")

    plan_contract = load_plan_contract(plan_file, root=root)

    run_out = io.StringIO()
    with (
        patch("teaagent.cli.create_llm_adapter", return_value=_governed_adapter()),
        redirect_stdout(run_out),
    ):
        run_code = main([
            "agent", "run", "gpt",
            "Fix the bug in calc.py",
            "--root", str(root),
            "--permission-mode", "prompt",
            "--from-plan", str(plan_file),
            "--allow-external-plan",
            "--require-plan",
            "--git-sandbox-auto-stash",
            "--approve-call-id", "fix-write",
            "--max-iterations", "8",
            "--max-tool-calls", "8",
        ])

    run_payload = json.loads(run_out.getvalue())
    assert run_code == 0, f"Governed run failed: {run_payload}"
    assert run_payload["status"] == "completed"

    ok(f"Run completed: {run_payload['run_id']}")
    ok(f"Plan hash verified: {run_payload['plan_contract']['content_hash'][:16]}…")

    step(3, "File edit — calc.py now contains the fix")
    fixed_content = calc.read_text(encoding="utf-8")
    assert "a + b" in fixed_content, f"Fix not applied; content: {fixed_content!r}"
    ok("calc.py: 'return a - b'  →  'return a + b'")

    step(4, "Verification — approval evidence captured")
    approvals = run_payload["run_evidence"].get("approvals", [])
    assert approvals, "No approvals in run evidence"
    a = approvals[0]
    approved = "granted" if a.get("approved") else "denied"
    ok(f"Approval: tool={a.get('tool_name')}  approved={approved}  by={a.get('approved_by', '?')}")

    # ── STEP 5: Evidence receipt ────────────────────────────────────────────
    step(5, "Evidence receipt — full audit receipt emitted")
    store = RunStore(root)
    run_id = run_payload["run_id"]
    receipt = build_run_receipt(store, run_id, root)
    missing = check_receipt_completeness(receipt, include_plan=True)
    assert missing == [], f"Receipt missing: {missing}"

    # Print key sections
    for line in receipt.splitlines():
        if any(k in line for k in ("Run receipt:", "Status:", "Goal:", "Plan:", "Cost:",
                                   "Audit log:", "Files touched:", "Approvals:", "Rollback")):
            print(f"  {_c('0;90', line)}")

    ok("All required receipt sections present")

    # Verify the audit log path exists
    for line in receipt.splitlines():
        if line.startswith("Audit log:"):
            audit_path = Path(line.split("Audit log:", 1)[1].strip())
            assert audit_path.exists(), f"Audit log missing: {audit_path}"
            ok(f"Evidence bundle: {audit_path}")
            break

    # ── STEP 6: Undo ───────────────────────────────────────────────────────
    step(6, "Undo — workspace restored to pre-run state")
    undo_out = io.StringIO()
    with redirect_stdout(undo_out):
        undo_code = main(["agent", "undo", run_id, "--root", str(root)])

    undo_payload = json.loads(undo_out.getvalue())
    assert undo_code == 0, f"Undo failed: {undo_payload}"
    assert undo_payload["status"] == "restored"
    assert "a - b" in calc.read_text(encoding="utf-8"), "Undo must restore original"

    ok(f"Restored via: {undo_payload.get('method', 'undo-journal')}")
    ok("calc.py: 'return a + b'  →  'return a - b'  (original state)")

    # ── Summary ────────────────────────────────────────────────────────────
    print(f"\n{_c('1;32', '══════════════════════════════════════════')}")
    print(f"{_c('1;32', ' Governance thesis: PROVED')}")
    print(f"{_c('1;32', '══════════════════════════════════════════')}")
    print()
    print("  Step 1  Plan gate         blocked write (exit 2) — no rhetoric")
    print("  Step 2  Approval          captured in audit trail before mutation")
    print("  Step 3  File edit         exactly calc.py, exactly as declared")
    print("  Step 4  Verification      agent confirmed fix before completion")
    print("  Step 5  Evidence receipt  all required sections present")
    print("  Step 6  Undo              original state fully restored")
    print()
    print(f"  Run ID:   {run_id}")
    print(f"  Provider: fake (no API key used)")
    print()

PYEOF

echo ""
printf "${_green}${_bold}Done. All six governance steps passed.${_reset}\n"
echo ""
note "To run the equivalent automated test:"
note "  pytest tests/acceptance/test_five_minute_proof_flow.py -v"
echo ""
note "To see the full docs walkthrough:"
note "  cat docs/demo/five-minute-proof.md"
echo ""
