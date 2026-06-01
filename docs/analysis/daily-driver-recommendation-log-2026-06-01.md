# Daily-Driver Review — Complete Recommendation & Thought Log
# 2026-06-01

**Purpose.** A single, durable log of **everything advised, suggested, recommended, or
judged** during the 2026-06-01 daily-driver review of teaagent (TUI / chat / agent
modes). Every entry has an ID, a type, the source it came from, the rationale, and a
status, so nothing said during the review is lost and each item is traceable to its
evidence and its fix.

**Legend.**
- **Type:** `FINDING` (defect in code) · `REC` (recommendation/fix) · `JUDGMENT`
  (assessment/opinion) · `RESEARCH` (external signal) · `DECISION-NEEDED` (maintainer
  call) · `ASSUMPTION` (stated premise) · `NON-GOAL` (recommended exclusion).
- **Status:** `OPEN` (no action yet) · `PLANNED` (in hardening plan) · `SPEC` (designed,
  not built) · `NEEDS-DECISION` · `NOTED` (advisory only).
- **Confidence:** H/M/L for findings and judgments.

Source docs referenced (all dated 2026-06-01 unless noted):
`FND` = code-grounded findings · `PLAN` = hardening plan · `RISK` = risk register ·
`REF` = competitive refresh · `JM` = persona journey maps · `CKP` = cockpit contract ·
`EVB` = evidence bundle spec · `PMR` = permission-mode risk table ·
`SURVEY` = market UX survey (2026-05-31) · `GAP` = ecosystem gap review (2026-05-31).

---

## 1. Findings (code defects)

| ID | Type | Conf | Statement | Evidence | Status | Fix |
|----|------|:----:|-----------|----------|--------|-----|
| CG-01 | FINDING | H | `teaagent chat` reports every task failed and never prints the answer | `chat_repl.py:820` `if result != 0:` vs `RunResult` | PLANNED | P0-1 |
| CG-02 | FINDING | H | REPL `/undo` runs `git checkout -- .`, destroying all uncommitted work | `chat_repl.py:418,789-799` | PLANNED | P0-2 |
| CG-03 | FINDING | H | `/cost`,`/budget` show fabricated/zero spend | REPL `+= 10` (`:563,825`); TUI `_session_cost_cents` never incremented (`tui:184`) | PLANNED | P1-1 |
| CG-04 | FINDING | M | REPL `/compact`,`/clear` act on a context the loop never fills | `chat_repl.py:564` only-path append | PLANNED | P1-2 |
| CG-05 | FINDING | H | Two divergent chat implementations cause behavior drift | `chat_repl.py` vs `tui/__init__.py` | PLANNED | P1-3 |
| CG-06 | FINDING | H | TUI "split-pane" clears screen each prompt, destroying scrollback | `tui:205` `\033[2J\033[H`, auto-on ≥120×30 (`:189`) | PLANNED | P1-4 |
| CG-07 | FINDING | H | TUI `compact` advertised but is a stub | help `:103` vs `_handle_compact :666` | PLANNED | P2-1 |
| CG-08 | FINDING | M | Two overlapping undo systems confuse recovery | TUI help `:76,:108` | PLANNED | P2-1 |
| CG-09 | FINDING | H | REPL `/background` is misleading + silently switches git branch | `chat_repl.py:130-132,150,640-648` | PLANNED | TICKET-3b |
| CG-10 | FINDING | H | Background suspension bypasses the audit chain | `chat_repl.py:85-96` (no `AuditLogger`) | PLANNED | TICKET-3b |

*(CG-09, CG-10 added in the second-pass reconsideration — see
`daily-driver-findings-second-pass-2026-06-01.md`. Severity re-exam there: CG-04 may
drop to P2 pending its test; CG-05 escalated in sequencing.)*

### Third-pass post-fix status (2026-06-01, after `ChatSessionController` landed)

**Closed/verified-fixed:** CG-01, CG-02, CG-03(REPL), CG-04, CG-06, CG-07, CG-09, CG-10.
CG-05 root-cause fix (the controller) exists and is correct **for the REPL only**.

| ID | Type | Conf | Statement | Evidence | Status | Fix |
|----|------|:----:|-----------|----------|--------|-----|
| CG-11 | FINDING | H | TUI `/cost`/budget always $0.00 — `_session_cost_cents` never incremented | `tui:186` init, only read; `_run_agent_task` 842-970 | OPEN | TICKET-12 |
| CG-12 | FINDING | H | TUI never adopted `ChatSessionController` → CG-05 divergence active | `tui:890` calls `run_chat_agent` directly | OPEN | TICKET-12 |
| CG-13 | FINDING | M | Controller swallows real `AttributeError/TypeError` as "mock detection" → hides undo-journal save failure | `chat_session_controller.py:143-159` | OPEN | TICKET-13 |
| CG-14 | FINDING | L | Redundant `audit_trail` JSON field on suspension (superseded by real audit event) | `chat_repl.py:89-93` vs `:129` | OPEN | TICKET-15 |
| CG-15 | FINDING | M | TUI `/undo` (git-stash) vs REPL `/undo` (UndoJournal) diverge; REPL help text stale | `tui:641-708`; `chat_repl.py:168` | OPEN | TICKET-12/15 |
| CG-16 | FINDING | H | A passing test masks CG-11 (injects cost, asserts display) | `tests/test_tui.py:1140-1145` | OPEN | TICKET-14 |

Full write-up: `daily-driver-third-pass-postfix-audit-2026-06-01.md`. New residual risks
R-6 (divergence active), R-7 (silent undo-save loss), R-8 (TUI green ≠ correct).

### Fourth-pass agent-mode / suspend→resume audit (2026-06-01)

Broadened to the previously un-reviewed agent surface. Suspension messaging is honest
(CG-09/10) but the advertised resume round-trip is broken.

| ID | Type | Conf | Statement | Evidence | Status | Fix |
|----|------|:----:|-----------|----------|--------|-----|
| AG-01 | FINDING | H | `teaagent resume <repl-suspend-id>` always errors (no `run_started` → `task_for_run` raises) | `chat_repl.py:56,130`; `run_store.py:143-149`; `_agent.py:217-220` | OPEN | TICKET-16 |
| AG-02 | FINDING | H | `agent run --background <id>` runs the id as a literal task, not a resume | `_agent.py:145`; `_agent_parsers.py:286`; positional `task` nargs='?' | OPEN | TICKET-16 |
| AG-03 | FINDING | M | No working "continue session" path; saved observations never rehydrated | `chat_repl.py:77-94` vs `_agent.py:239-244` | OPEN | TICKET-16 |
| AG-04 | FINDING | M | 3 inconsistent follow-up commands undercut the CG-09/10 honesty fix | `chat_repl.py:142,143,662` | OPEN | TICKET-16 |

Agent-mode governance verified solid (scoped approvals, plan gate, auto-compact). Full
write-up: `daily-driver-agent-mode-suspension-audit-2026-06-01.md`.

### Fifth-pass: test-catalog grounding (2026-06-01)

| ID | Type | Conf | Statement | Evidence | Status | Fix |
|----|------|:----:|-----------|----------|--------|-----|
| CG-17 | FINDING | H | `test_chat_surface_parity` claims CG-05 TUI parity but builds two controllers and never instantiates `TeaAgentTUI` | `tests/test_cli_chat.py:483-552` | OPEN(test) | TICKET-12b |

Catalog also found **5 shipped fixes with no named guard test** (CG-02, CG-03-REPL, CG-04,
CG-09, CG-10). Full: `daily-driver-acceptance-test-catalog-2026-06-01.md`,
`daily-driver-findings-status-ledger-2026-06-01.md`.

## 2. Recommendations (fixes) — from PLAN

| ID | Type | Statement | Closes | Status |
|----|------|-----------|--------|--------|
| P0-1 | REC | Branch on `result.status`; print `final_answer`; record turn | CG-01 | PLANNED |
| P0-2 | REC | Remove `git checkout -- .`; route undo through `UndoJournal`/checkpointed files only | CG-02 | PLANNED |
| P1-1 | REC | Accumulate session cost from `RunResult.cost_cents`; show tokens; label server-reported | CG-03 | PLANNED |
| P1-2 | REC | Record each turn into `session_context`; make compaction operate on real history | CG-04 | PLANNED |
| P1-3 | REC | Extract shared `ChatSessionController`; both surfaces become I/O only | CG-05 | PLANNED |
| P1-4 | REC | Real fixed-region TUI layout OR drop auto-clear; never clear on large terminals | CG-06 | PLANNED |
| P2-1 | REC | One operator-facing `undo` (UndoJournal); rename git-stash to `checkpoint restore`; wire TUI compact | CG-07, CG-08 | PLANNED |

## 3. Recommendations (design specs)

| ID | Type | Statement | Source | Closes gap | Status |
|----|------|-----------|--------|-----------|--------|
| SPEC-JM | REC | Persona journey maps + journey→acceptance matrix | JM | F-ECO-002 | SPEC |
| SPEC-CKP | REC | Single `CockpitState` producer; CLI/TUI/dashboard render-only; parity tests | CKP | F-ECO-010 | SPEC |
| SPEC-EVB | REC | Run-evidence bundle extending `summarize_run`; derivations cannot hallucinate | EVB | F-ECO-011 | SPEC |
| SPEC-PMR | REC | Single permission-mode risk decision table; surface×mode consistency doc-lint | PMR | F-ECO-013 | SPEC |
| SPEC-IDE | REC | CLI-first; thin governed VS Code parity bridge + attach recipe; desktop as decision | ide-desktop-surface-plan | F-ECO-004 | SPEC |
| SPEC-MCP | REC | MCP trust journey: default-deny unknown, expiry fails-closed, explicit revoke, audited | mcp-trust-onboarding-journey | F-ECO-008 | SPEC |
| SPEC-AUTO | REC | Automation lifecycle state machine + verbs (promote/pause/resume/expire/transfer/explain-skip) | automation-lifecycle-spec | F-ECO-012 | SPEC |
| SPEC-PROV | REC | LLM `ModelFallbackPolicy` mirroring knowledge fallback; never widen risk on fallback | provider-resilience-playbook | F-ECO-009 | SPEC |
| SPEC-REPO | REC | Repo-map benchmark corpus (top-K/MRR/latency/failure-class) + nightly→release gate | repo-map-benchmark-corpus | F-ECO-005 | SPEC |
| SPEC-SUB | REC | Parent multi-child review→compare→apply-one→conflict→record journey | subagent-parent-review-workflow | F-ECO-006 | SPEC |
| SPEC-EXT | REC | Unified `explain activation` aggregating hook/skill/plugin/MCP reasons; session-scoped disable | extension-activation-explainability | F-ECO-007 | SPEC |

## 4. Judgments (assessments made during review)

| ID | Type | Conf | Judgment | Basis |
|----|------|:----:|----------|-------|
| J-1 | JUDGMENT | H | The May-31 corpus is strong; regenerating it would be padding — value is code grounding | corpus read |
| J-2 | JUDGMENT | H | CG-01 is a 60-second switching-trigger; first-impression correctness gates adoption | SURVEY UX-F5 + REF D-3 |
| J-3 | JUDGMENT | H | CG-02 (data loss) is the only irreversible item → the release blocker | RISK PR-1 |
| J-4 | JUDGMENT | M | Fabricated cost (CG-03) is worse than no cost display — teaches distrust | REF D-1 |
| J-5 | JUDGMENT | H | CG-05 (two implementations) is the *root cause* enabling CG-01/02/03 | code structure |
| J-6 | JUDGMENT | M | TUI panel is the always-on surface yet least complete cockpit — an inversion | CKP parity matrix |
| J-7 | JUDGMENT | H | Governance-first remains the durable differentiator; gaps are *legibility* not capability | SURVEY §7, GAP decision |
| J-8 | JUDGMENT | M | P-SEC is teaagent's strongest persona; P-DEV is the most broken | JM |
| J-9 | JUDGMENT | M | Phase 0 (P0-1/P0-2) is the highest impact-to-effort work in the repo right now | PLAN effort |
| J-10 | JUDGMENT | M | An IDE/desktop plan was deliberately NOT written — would be ungrounded speculation | scope discipline |

## 5. Research signals (external, sourced)

| ID | Type | Signal | Source |
|----|------|--------|--------|
| D-1 | RESEARCH | Cost/token *accuracy* is now a competitive axis (cache-aware, server vs tiktoken) | Hermes #504, tokscale, Codeburn, DeepSeek-TUI |
| D-2 | RESEARCH | REPL rendering fragility (resize/scrollback) is a named switching reason | Nimbalyst, Thomas Wiegold |
| D-3 | RESEARCH | Defection narratives are fast + multi-surface (DeepSeek-TUI +580★/24h) | AgentConn, GitHub |
| D-4 | RESEARCH | Governance-first / agent-identity standardization unchanged as differentiator | (no contradicting signal) |

## 6. Decisions needed (maintainer)

See `daily-driver-open-decisions-2026-06-01.md` for the full register. IDs: DQ-1…DQ-7.

## 7. Assumptions & non-goals

See `daily-driver-assumptions-and-nongoals-2026-06-01.md`. IDs: AS-1…AS-6, NG-1…NG-5.

---

## Status roll-up

- **16 findings** (CG-01…CG-16). CG-01/02/03(REPL)/04/06/07/09/10 now **FIXED** by the
  maintainer's `ChatSessionController` batch; **CG-11…CG-16 OPEN** (TUI not migrated).
- **4 design specs**, all SPEC (designed, unbuilt).
- **10 judgments** logged with basis.
- **4 research signals** sourced.
- Code **was** changed since this review opened (the controller + REPL fixes); the
  third-pass audit re-anchored all findings against current HEAD.

## Next concrete action (if approved to implement)

Hardening **Phase 0**: P0-1 (CG-01) and P0-2 (CG-02) — small, shippable without the
refactor, each with a falsifiable regression test. Everything else can follow.
</content>
