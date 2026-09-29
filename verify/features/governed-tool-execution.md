---
feature: governed-tool-execution
source_commit: dc60c1eb
last_verified_at: 2026-09-29
verification_status: passed
covers:
  - teaagent/policy.py
  - teaagent/tools.py
  - teaagent/tool_permissions.py
  - teaagent/runner/_governed_execution.py
  - teaagent/ergonomics/_approval_grants.py
  - teaagent/ergonomics/_approval_state.py
  - teaagent/cli/_handlers/_agent/config.py
  - teaagent/cli/_handlers/_ergonomics/approval.py
  - teaagent/plan.py
drive:
  - id: tests
    expect: governance/policy/approval test set passes (~200 tests, ~12s)
    run: |
      cd "$REPO"
      "$P" -m pytest -q tests/policy tests/approval tests/test_policy.py \
        tests/test_approval_token_exactness.py tests/test_scoped_payload_preapproval.py \
        tests/test_preapproved_call_ids_removal.py tests/test_efx003_one_time_approval.py \
        tests/test_governance_hardening.py tests/test_governance_permission_binding.py \
        tests/test_phase4_tool_permissions.py
  - id: tool-contracts
    expect: every registered tool carries name, description and the three annotations; lint reports zero errors; write/patch/shell tools are destructive
    run: |
      "$T" tool lint --root . | jget 'd["error_count"]' | grep -qx 0
      "$T" tool list --root . > tools.json
      jget 'all(set(t["annotations"]) >= {"destructive","idempotent","read_only"} and t["name"] and t["description"] for t in d["tools"])' < tools.json | grep -qx True
      jget 'sorted(t["name"] for t in d["tools"] if t["annotations"]["destructive"])' < tools.json > destructive.txt
      for name in workspace_write_file workspace_apply_patch workspace_run_shell workspace_run_shell_mutate workspace_edit_at_hash; do grep -q "'$name'" destructive.txt; done
  - id: read-only-blocks-write
    expect: read-only run exits 1, audit records tool_call_blocked, probe.txt is never created
    run: |
      rc=0; TEAAGENT_FAKE_SCRIPT="$FIX/write-probe.json" "$T" run fake "write probe" --root . --permission-mode read-only --json --no-summary > out.json 2> /dev/null || rc=$?
      [ "$rc" = 1 ]
      jget '"tool_call_blocked" in d["audit_summary"]["event_counts"]' < out.json | grep -qx True
      [ ! -e probe.txt ]
  - id: prompt-pauses-unapproved-write
    expect: prompt-mode run without approval exits 1 with status pending_approval; `approval pending` lists call c1; no file written
    run: |
      rc=0; TEAAGENT_FAKE_SCRIPT="$FIX/write-probe.json" "$T" run fake "write probe" --root . --permission-mode prompt --json --no-summary > out.json 2> /dev/null || rc=$?
      [ "$rc" = 1 ]
      jget 'd["audit_summary"]["status"]' < out.json | grep -qx pending_approval
      "$T" approval pending --root . | jget '[p["call_id"] for p in d["pending"]]' | grep -q "'c1'"
      [ ! -e probe.txt ]
  - id: scoped-digest-exactness
    expect: --approve-scoped with the exact payload digest (compute_scoped_payload_digest) runs the write; any other digest leaves the call pending
    run: |
      wrong=$(printf '0%.0s' $(seq 64))
      TEAAGENT_FAKE_SCRIPT="$FIX/write-probe.json" "$T" run fake "write probe" --root . --permission-mode prompt --approve-scoped "workspace_write_file:$wrong" --json --no-summary 2> /dev/null > out.json || true
      jget 'd["audit_summary"]["status"]' < out.json | grep -qx pending_approval
      [ ! -e probe.txt ]
      digest=$("$P" -c "from teaagent.policy import compute_scoped_payload_digest as c; print(c('workspace_write_file', {'path': 'probe.txt', 'content': 'x'}))")
      TEAAGENT_FAKE_SCRIPT="$FIX/write-probe.json" "$T" run fake "write probe" --root . --permission-mode prompt --approve-scoped "workspace_write_file:$digest" --json --no-summary 2> /dev/null > out.json
      jget 'd["audit_summary"]["status"]' < out.json | grep -qx completed
      [ "$(cat probe.txt)" = x ]
  - id: approve-and-resume
    expect: "`approval approve c1 --resume` resumes the paused run as a new completed run that performs the write, without the inert --approve-call-id deprecation notice"
    run: |
      TEAAGENT_FAKE_SCRIPT="$FIX/write-probe.json" "$T" run fake "write probe" --root . --permission-mode prompt --json --no-summary > /dev/null 2>&1 || true
      TEAAGENT_FAKE_SCRIPT="$FIX/write-probe.json" "$T" approval approve c1 --resume --root . > out.json 2> err.txt
      jget 'd["audit_summary"]["status"], bool(d["resumed_from"])' < out.json | grep -qx "('completed', True)"
      ! grep -q 'approve-call-id' out.json err.txt
      [ -e probe.txt ]
  - id: presets-deny-beats-allow
    expect: with an allow grant on src/** and a deny grant on src/secret/**, `approval check` answers allow for src/a.py and deny for src/secret/k.py
    run: |
      "$T" approval grant workspace_write_file --path-glob 'src/**' --scope session --root . > /dev/null
      "$T" approval deny workspace_write_file --path-glob 'src/secret/**' --root . > /dev/null
      "$T" approval check workspace_write_file --path src/a.py --permission-mode prompt --root . | jget 'd["decision"]' | grep -qx allow
      "$T" approval check workspace_write_file --path src/secret/k.py --permission-mode prompt --root . | jget 'd["decision"]' | grep -qx deny
  - id: plan-gate
    expect: workspace-write without a plan fails fast with PLAN_GATE (exit 2); `plan` on an ambiguous task still writes the artifact but exits 2 (ready=false); a run bound to a plan that lists no files blocks the write as intent drift
    run: |
      rc=0; TEAAGENT_FAKE_SCRIPT="$FIX/write-probe.json" "$T" run fake "write probe" --root . --permission-mode workspace-write --json --no-summary > out.txt 2>&1 || rc=$?
      [ "$rc" = 2 ]; grep -q PLAN_GATE out.txt; [ ! -e probe.txt ]
      rc=0; "$T" plan "write probe" --root . --permission-mode workspace-write > plan.json 2> /dev/null || rc=$?
      [ "$rc" = 2 ]; jget 'd["ready"]' < plan.json | grep -qx False
      plan=$(ls .teaagent/plans/*.md)
      TEAAGENT_FAKE_SCRIPT="$FIX/write-probe.json" "$T" run fake --from-plan "$plan" --require-plan --root . --permission-mode workspace-write --json --no-summary > /dev/null 2>&1 || true
      [ ! -e probe.txt ]
      grep -h '"tool_call_blocked"' .teaagent/runs/*.jsonl | grep -q 'Intent drift'
---

# Governed tool execution

Every tool call passes `ApprovalPolicy` (`teaagent/policy.py`) through
`authorize_tool_call` (`teaagent/runner/_governed_execution.py`) before
`ToolRegistry.execute()` (`teaagent/tools.py`). This feature covers permission
modes, exact-call approval, approval presets, and the plan-before-write gate
for `teaagent run` / `agent run`.

## Entry points

| Surface | Command / symbol |
|---|---|
| Permission modes | `teaagent run --permission-mode {read-only,workspace-write,prompt,allow,danger-full-access}` |
| Exact-call approval | `--approve-scoped TOOL:SHA256`; digest = `teaagent.policy.compute_scoped_payload_digest(tool_name, arguments)` (sha256 of canonical `{"arguments":…,"tool_name":…}`) |
| Pending approvals | `teaagent approval pending`, `approval approve <call_id> --resume`, `approval reject`, `approval why-denied <run_id>` |
| Presets | `teaagent approval grant|deny|check|list|revoke` → `.teaagent/approvals.json`; order deny → allow → prompt |
| Plan gate | `_require_plan_gate` (`cli/_handlers/_agent/config.py`); `teaagent plan` writes `.teaagent/plans/*.md`; `run --from-plan … --require-plan` |
| Tool contracts | `teaagent tool list|inspect|lint` |

## Observable outcomes (healthy product)

- `read-only`: a destructive call is blocked, run exits 1, audit has `tool_call_blocked` with reason `read_only_mode`. A session grant does **not** override read-only in a real run.
- `prompt`: an unapproved destructive call pauses the run (`status: pending_approval`, exit 1, `run_paused` event). Nothing is written.
- `--approve-scoped` approves only the call whose tool+arguments digest matches exactly. The audit event's `argument_digest` (v2) is a **different** digest; do not use it for `--approve-scoped`.
- `--approve-call-id` is inert (prints a deprecation notice, grants nothing).
- `workspace-write` without a bound plan exits 2 with `Error [PLAN_GATE]`; `--skip-plan-check` bypasses the gate (not recommended).
- A plan whose "Files likely touched" section inferred no paths blocks every write as "Intent drift".

## Failure paths

| Symptom | Likely class |
|---|---|
| destructive call runs in read-only/prompt without approval | product regression (AGENTS.md Tool Governance) |
| wrong digest approves a call | product regression |
| `approval check` output shape changed but runs still gate correctly | doc drift |
| fake script ignored (run answers "Fake response" with no tool call) | harness failure: `TEAAGENT_FAKE_SCRIPT` path unreadable or not a JSON list |

## Known quirks (healthy)

- `approval check --permission-mode read-only` reports `allow` when a grant matches; it evaluates presets only. The real run still blocks (see `read-only-blocks-write`).

## Evidence

`verify/checks/drive.sh governed-tool-execution` → one PASS/FAIL line per drive id plus a log directory.
