# Daily-Driver Usefulness Master Plan

Date: 2026-06-01

Goal: make TeaAgent reasonably useful for daily TUI, TUI chat, CLI chat, and agent-mode
workflows by prioritizing correctness, stability, recoverability, and UX clarity.

## Product Thesis

TeaAgent should compete as a governance-first local agent harness: thin orchestration,
clear tool authority, auditable runs, portable skills, and recoverable edits. The daily
experience should feel calmer than large IDE agents and safer than raw terminal scripts.

## Non-Goals

- Do not add another agent framework.
- Do not optimize for a decorative TUI before state correctness.
- Do not hide cost or permission complexity behind vague "smart" behavior.
- Do not claim background execution when the system only saved a checkpoint.

## Definition Of Ready

A daily surface is ready when:

1. The first command does what help says it does.
2. Cost and budget values are real or clearly unavailable.
3. Undo state is visible before and after edits.
4. Branch/sandbox state is explicit.
5. Background, attach, resume, and suspend have distinct behavior and copy.
6. Tests exercise the same code path users run.
7. Docs are generated or validated against current behavior.

## Phase 0: Stop Misleading Users

| Ticket | Scope | Acceptance |
|---|---|---|
| DU-001 | Fix or reject `teaagent chat <task>`. | Supplying a task executes it through the same controller path as interactive chat, or returns a clear unsupported-syntax error. |
| DU-002 | Wire TUI cost ledger. | A mocked successful TUI chat run with `cost_cents=123` makes `/cost` show `$1.23` and budget remaining update. |
| DU-003 | Resolve git-sandbox contract. | Tests prove branch switching occurs only under the documented default/flag/consent path. |
| DU-004 | Rename/correct suspension output. | `/background` no longer says work continues unless it does; help uses `suspend` for checkpoints. |
| DU-005 | Update acceptance count docs. | `python3 scripts/validate_docs_consistency.py` passes. |

## Phase 1: Unify The State Model

| Ticket | Scope | Acceptance |
|---|---|---|
| DU-006 | Make TUI chat use `ChatSessionController`. | TUI and CLI chat share run result handling, cost, observations, and undo. |
| DU-007 | Quarantine stale `_chat.py` REPL code. | Runtime imports are audited; stale function is deleted or made private with no external references. |
| DU-008 | Create one daily command grammar. | Docs and parser tests agree on provider/task order for `run`, `chat`, `tui`, `resume`, `attach`, and `undo`. |
| DU-009 | Recovery decision tree. | Docs and help describe undo preview, undo restore, resume, attach, background, checkpoint, and suspend. |
| DU-010 | Approval copy taxonomy. | Setup, provider missing, approval blocked, budget exceeded, undo unavailable, and unknown command have tested messages. |

## Phase 2: Daily Cockpit

| Ticket | Scope | Acceptance |
|---|---|---|
| DU-011 | TUI cockpit contract. | Headless tests assert provider/model, permission, branch, cost, budget, last run, undo, and active rules. |
| DU-012 | Cost and token trend. | Session display shows per-run cost, session total, and budget remaining from one source of truth. |
| DU-013 | Run evidence bundle. | Every agent run exposes changed files, tools used, approvals granted, tests run, and undo journal status. |
| DU-014 | Long-run heartbeat. | Background/agent runs show current tool, elapsed time, cost estimate, and next checkpoint. |
| DU-015 | Context compaction preview. | User can inspect what will be kept/dropped before compacting. |

## Phase 3: Trust And Ecosystem Hardening

| Ticket | Scope | Acceptance |
|---|---|---|
| DU-016 | MCP trust policy. | Unknown remote MCP tools default to explicit prompt unless a local trust policy says otherwise. |
| DU-017 | Skill/rule inspectability. | TUI and run evidence list active skills, project instructions, and memory sources. |
| DU-018 | First-hour smoke script. | Script exercises setup, chat task, TUI chat, undo, cost, and docs consistency. |
| DU-019 | Forum-feedback watchlist. | Docs track recurring competitor pain points: cost, slowness, rules ignored, context drift, rollback anxiety. |
| DU-020 | Readiness badge discipline. | README daily-driver claims are gated on tests and current truth audit. |

## Verification Commands

Run these before claiming daily-driver readiness:

```bash
python3 -m pytest tests/test_cli_chat.py tests/test_tui.py tests/test_docs_consistency.py -q
python3 scripts/validate_docs_consistency.py
teaagent tool lint --root .
```

For branch/sandbox changes, add a temporary clean-repo integration test before changing
docs or defaults.

## Release Criteria

TeaAgent can be described as daily-useful when Phase 0 and Phase 1 are complete, the
verification commands pass, and README/docs no longer contradict runtime behavior.

