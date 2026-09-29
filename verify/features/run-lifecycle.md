---
feature: run-lifecycle
source_commit: dc60c1eb
last_verified_at: 2026-09-29
verification_status: passed
covers:
  - teaagent/runner/
  - teaagent/budget.py
  - teaagent/run_store.py
  - teaagent/run_undo.py
  - teaagent/sandbox/_git_branch.py
  - teaagent/llm/_fake_adapter.py
  - teaagent/cli/_handlers/_agent/
  - teaagent/cli/_handlers/_replay.py
drive:
  - id: tests
    expect: runner/budget/run-store/undo/resume/sandbox/replay test set passes (~155 tests, ~20s)
    run: |
      cd "$REPO"
      "$P" -m pytest -q tests/runner tests/test_run_store.py tests/test_budget.py \
        tests/test_scope_budget_fail_closed.py tests/test_undo_mechanism.py \
        tests/test_task002_undo_honesty.py tests/test_resume_lifecycle.py \
        tests/test_git_sandbox.py tests/test_replay_cli.py
  - id: offline-run-completes
    expect: unscripted fake run completes in one iteration with final answer "Fake response" and a persisted JSONL log
    run: |
      "$T" run fake "say hi" --root . --json --no-summary > out.json 2> /dev/null
      jget 'd["audit_summary"]["status"], d["iterations"], d["final_answer"]' < out.json | grep -qx "('completed', 1, 'Fake response')"
      [ -s ".teaagent/runs/$(jget 'd["run_id"]' < out.json).jsonl" ]
  - id: iteration-cap
    expect: a 4-tool-call script under --max-iterations 2 fails (exit 1) with run_failed "iteration budget exceeded"
    run: |
      rc=0; TEAAGENT_FAKE_SCRIPT="$FIX/four-reads.json" "$T" run fake "list" --root . --permission-mode read-only --max-iterations 2 --json --no-summary > out.json 2> /dev/null || rc=$?
      [ "$rc" = 1 ]
      grep -h '"run_failed"' ".teaagent/runs/$(jget 'd["run_id"]' < out.json).jsonl" | grep -q 'iteration budget exceeded'
  - id: tool-call-cap
    expect: the same script under --max-tool-calls 2 fails after exactly 2 completed tool calls with "tool-call budget exceeded"
    run: |
      rc=0; TEAAGENT_FAKE_SCRIPT="$FIX/four-reads.json" "$T" run fake "list" --root . --permission-mode read-only --max-tool-calls 2 --json --no-summary > out.json 2> /dev/null || rc=$?
      [ "$rc" = 1 ]
      jget 'd["audit_summary"]["event_counts"]["tool_call_completed"]' < out.json | grep -qx 2
      grep -h '"run_failed"' ".teaagent/runs/$(jget 'd["run_id"]' < out.json).jsonl" | grep -q 'tool-call budget exceeded'
  - id: runs-list-and-replay
    expect: "`runs --root . list` shows the run as completed; `runs --root . replay <id>` is a dry-run trace naming the tools used"
    run: |
      TEAAGENT_FAKE_SCRIPT="$FIX/four-reads.json" "$T" run fake "list" --root . --permission-mode read-only --json --no-summary > out.json 2> /dev/null
      id=$(jget 'd["run_id"]' < out.json)
      "$T" runs --root . list | jget "[r['status'] for r in d if r['run_id'] == '$id']" | grep -qx "\['completed'\]"
      "$T" runs --root . replay "$id" | jget 'd["mode"], sorted(set(d["tools_used"]))' | grep -qx "('dry-run', \['workspace_list_files'\])"
  - id: undo-restores
    expect: after an approved write, `undo --preview` shows the diff and `undo` deletes the created file (status restored)
    run: |
      TEAAGENT_FAKE_SCRIPT="$FIX/write-probe.json" "$T" run fake "write probe" --root . --permission-mode workspace-write --skip-plan-check --json --no-summary > /dev/null 2>&1
      [ -e probe.txt ]
      "$T" undo --preview --root . | grep -q '^+++ b/probe.txt'
      "$T" undo --root . 2> /dev/null | jget 'd["status"], d["deleted"]' | grep -qx "('restored', \['probe.txt'\])"
      [ ! -e probe.txt ]
---

# Run lifecycle

`teaagent run` / `agent run` builds an `AgentRunner` (`teaagent/runner/_core.py`)
with a `RunBudget` (`teaagent/budget.py`), persists every event through
`RunStore` (`teaagent/run_store.py`) to `.teaagent/runs/<run_id>.jsonl`, and
journals workspace edits for `teaagent undo` (`teaagent/run_undo.py`).

## Offline driving

The `fake` provider (`teaagent/llm/_fake_adapter.py`) needs no key. With no
script it answers one `final` decision ("Fake response"). Set
`TEAAGENT_FAKE_SCRIPT=<file.json>` to a JSON list of
`{"type":"tool","tool_name":…,"arguments":{…},"call_id":…}` /
`{"type":"final","content":…}` entries to script tool calls. Fixtures:
`verify/fixtures/write-probe.json` (one destructive write),
`verify/fixtures/four-reads.json` (four read-only calls). An unreadable or
non-list script silently falls back to the default answer.

## Entry points

| Surface | Command / symbol |
|---|---|
| Run | `teaagent run fake "<task>" --root . --json --no-summary` |
| Caps | `--max-iterations N`, `--max-tool-calls N`, `--max-estimated-cost-cents N` (defaults from `.teaagent/config.toml`: 10 / 10) |
| History | `teaagent runs --root . list|show|trace|replay|export <id>` |
| Resume | `teaagent resume [provider] <run_id>`; `approval approve <call_id> --resume` |
| Undo | `teaagent undo [--preview] [run_id] --root .` |

## Observable outcomes (healthy product)

- Every run ends in a terminal status recorded in the JSONL (`run_completed`, `run_failed`, or `run_paused`).
- Exceeding a cap is `run_failed` with category `model_logic` and message `iteration budget exceeded` / `tool-call budget exceeded`; exit 1.
- `undo` restores via the journal; `--preview` prints a unified diff without applying it.

## Failure paths

| Symptom | Likely class |
|---|---|
| run continues past a cap | product regression (AGENTS.md Runtime Safety) |
| run missing from `runs list` or JSONL absent | product regression |
| `Git sandbox initialization failed: Worktree is dirty` warning | harness: scratch tree dirty; runs still execute |
| `teaagent: error: unrecognized arguments: --root .` on `runs list --root .` | harness/doc: `--root` belongs **before** the `runs` subcommand |

## Known quirks (healthy)

- `undo` prints `[TeaAgent WARNING] checkpoint restore failed: Git sandbox not properly initialized, falling back to UndoJournal` on stderr and still restores (`mechanism: journal undo`).
- Scratch workspaces must be committed git repos, otherwise the auto git sandbox warns.

## Evidence

`verify/checks/drive.sh run-lifecycle`.
