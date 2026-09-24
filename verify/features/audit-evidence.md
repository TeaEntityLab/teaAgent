---
feature: audit-evidence
source_commit: ba6009df
last_verified_at: 2026-09-24
verification_status: passed
covers:
  - teaagent/audit.py
  - teaagent/audit_chain.py
  - teaagent/audit_export.py
  - teaagent/run_store.py
  - teaagent/cli/_handlers/_audit.py
drive:
  - id: tests
    expect: audit/chain/export/schema test set passes (~128 tests, ~9s)
    run: |
      cd "$REPO"
      "$P" -m pytest -q tests/test_audit.py tests/test_ws3_strict_audit_chain.py \
        tests/test_ws3_audit_chain_remaining.py tests/test_audit_export.py \
        tests/test_audit_schema_conformance.py tests/test_dogfood_audit_release_g25_g28.py
  - id: lifecycle-events-recorded
    expect: an approved write run logs run_started, tool_call_requested, tool_call_started, tool_call_completed, run_completed; tool_call_* events redact the file content (every event, including nested h4_governance_shadow arguments, is checked by oracle A6)
    run: |
      TEAAGENT_FAKE_SCRIPT="$FIX/write-probe.json" "$T" run fake "write probe" --root . --permission-mode workspace-write --skip-plan-check --json --no-summary > out.json 2> /dev/null
      log=".teaagent/runs/$(jget 'd["run_id"]' < out.json).jsonl"
      for e in run_started tool_call_requested tool_call_started tool_call_completed run_completed; do grep -q "\"event_type\": \"$e\"" "$log"; done
      "$P" - "$log" <<'PY'
      import json, sys
      events = [json.loads(line) for line in open(sys.argv[1])]
      calls = [e for e in events if e['event_type'].startswith('tool_call_')]
      assert calls and all(e['payload']['arguments']['content'] == '[redacted]' for e in calls if 'arguments' in e['payload'])
      PY
  - id: chain-verify-and-tamper
    expect: "`audit verify <id> --ci` reports valid (exit 0); flipping one event_type in a copy reports invalid (exit 1)"
    run: |
      "$T" run fake "say hi" --root . --json --no-summary > out.json 2> /dev/null
      id=$(jget 'd["run_id"]' < out.json)
      "$T" audit verify "$id" --root . --ci | jget 'd["status"]' | grep -qx valid
      sed 's/"iteration_started"/"iteration_startedX"/' ".teaagent/runs/$id.jsonl" > tampered.jsonl
      rc=0; "$T" audit verify --path tampered.jsonl --root . --ci > verdict.json 2> /dev/null || rc=$?
      [ "$rc" = 1 ]; jget 'd["status"]' < verdict.json | grep -qx invalid
  - id: denial-explained
    expect: "a read-only blocked write is explained by `approval why-denied <run_id>` with reason read_only_mode"
    run: |
      TEAAGENT_FAKE_SCRIPT="$FIX/write-probe.json" "$T" run fake "write probe" --root . --permission-mode read-only --json --no-summary > out.json 2> /dev/null || true
      "$T" approval why-denied "$(jget 'd["run_id"]' < out.json)" --root . | grep -q 'Reason:   read_only_mode'
---

# Audit and evidence

`AuditLogger` (`teaagent/audit.py`) writes one hash-chained JSONL per run
(`.teaagent/runs/<run_id>.jsonl`): each event carries `hash`, `prev_hash`, and
`chain_hmac` keyed by a per-run key under `$HOME/.teaagent/run-keys/`.
`verify_audit_chain` (`teaagent/audit_chain.py`) backs `teaagent audit verify`.

## Entry points

| Surface | Command |
|---|---|
| Verify | `teaagent audit verify [<run_id>] [--path FILE] --root . --ci` (JSON `{"event_count", "status": "valid"}`, exit 0; or `{"event_count", "failure_count", "status": "invalid"}`, exit 1) |
| Inspect | `teaagent audit list|show|tail`, `teaagent runs --root . show|trace <id>` |
| Export | `teaagent audit export <run_id> --root . [-o FILE]` |
| Denials | `teaagent approval why-denied <run_id> [--call-id ID] [--verbose] --root .` |

## Observable outcomes (healthy product)

- Every tool call and the final result appear as events (AGENTS.md Runtime Safety).
- Tool arguments that carry content are redacted (`"content": "[redacted]"`).
- Any byte change to an event breaks `audit verify` (`status: invalid`, exit 1 under `--ci`).

## Failure paths

| Symptom | Likely class |
|---|---|
| tampered log verifies valid | product regression |
| tool call executed but no `tool_call_*` event | product regression |
| `HMAC chain key not found at …/run-keys/<name>.key` on `--path` copies | healthy: the key is looked up by file stem; hash chain still checked |
| `legacy event without chain fields` lines when verifying `runs-index.jsonl` | healthy: the index is not a chained run log; verify run ids, not the index |

## Evidence

`verify/checks/drive.sh audit-evidence`.
