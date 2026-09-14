# Risk Report — `audit verify` accepts run_id / --path

**Date:** 2026-09-14 · **Scope:** `teaagent/cli/_handlers/_audit.py` `audit_verify_command` + `teaagent/cli/_misc_parsers/diagnostics.py` `audit verify` parser
**High-risk path touched:** `teaagent/cli/_handlers/_audit.py` (audit verification surface)

## What changes

`audit verify` was hardcoded to `.teaagent/audit.jsonl`, a workspace-global log
that no code path writes — runs persist to `.teaagent/runs/<run_id>.jsonl`.
The command therefore always exited 1 with "Audit log not found" on a real
workspace, making the chain-verification surface unreachable.

`audit verify` now accepts an optional `run_id` positional and a `--path`
option. Resolution precedence: `--path` > `run_id` (per-run store log) > the
global `.teaagent/audit.jsonl`. When the global log is absent but per-run logs
exist, the not-found error now names the `run_id`/`--path` forms.

## Risk assessment

- **Blast radius:** read-only. `verify_audit_chain` only reads the file; no
  audit data is mutated. The change is which file is opened.
- **Failure mode:** a wrong `run_id`/`--path` resolves to a nonexistent file and
  returns the same "not found" error as before — no new failure class.
- **Backward compatibility:** bare `audit verify` still targets the global log
  and still exits 1 when absent; the only difference is a more actionable
  message. `--signature` attestation and `--ci` JSON output are unchanged.
- **Rollback:** revert the hunk; `run_id`/`--path` become absent and the command
  returns to the hardcoded global path.

## Decision

Proceed. The command was dead code on every real workspace; this makes the
existing `verify_audit_chain` machinery reachable for the per-run logs that
actually get written.
