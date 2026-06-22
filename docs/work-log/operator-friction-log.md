# Operator Friction Log

> **Status:** Active intake log.
> **Evidence boundary:** Owner-written entries are evidence. Agent-written
> competitor or community entries are hypotheses until the owner validates or
> rejects them in real TeaAgent use.
> **Derived from:** [Harness-First Direction](../strategy/harness-first-direction-2026-06-13.md).

## Purpose

This log is the intake surface for owner-operator friction. It keeps TeaAgent's
UX work tied to real harness use instead of competitor feature parity.

## Current Intake Status

- Owner evidence entries: 5 (F2/F3/F6/F7/F8 confirmed; F1/F4/F5 not confirmed).
- Competitor-derived hypotheses: 7 open (none closed — a promoted hypothesis links to its owner-evidence entry rather than self-closing).
- Direction implication: UX work may cite owner evidence entries below; harness-first §5.2 seeds F2/F3 are now owner-validated.

Use this log when:

- the owner hits friction while asking, approving, undoing, resuming, reading a
  receipt, checking cost, or understanding why a run was allowed or blocked
- a competitor UX pattern suggests a possible ergonomics problem, but TeaAgent
  has not validated it locally
- a prior friction entry is closed by a commit, test, or documentation change

## Entry Rules

- Owner-written entries are evidence.
- Agents may add only competitor-derived or community-derived hypothesis entries.
- Hypothesis entries must be tagged `[hypothesis: source, date]`.
- Hypothesis entries must not become roadmap truth until the owner confirms the
  friction in real use or repository evidence shows a governance gap.
- A closed entry must cite the commit, test, or document that resolved it; `n/a`
  is allowed only for open or rejected entries.
- A promoted entry must cite the ticket or acceptance-gap artifact in
  `Promoted to`; `n/a` is allowed only before promotion or for rejected entries.
- Closing promoted work requires both links: the downstream artifact in
  `Promoted to` and the commit/test/doc in `Closure evidence`.
- Do not use this log for public positioning, competitor ranking, or feature
  parity requests.
- Agents may ask the intake prompts below, but must not answer them on the
  owner's behalf.

## Quick Capture

Use one dated line while the friction is fresh. Expand it with the structured
fields only when the entry is promoted to work.

```markdown
### YYYY-MM-DD - Short title

- **Type:** evidence | hypothesis
- **Source:** owner real use | [hypothesis: source, date]
- **One-line capture:** I tried __; expected __; got __.
- **Status:** open | closed | rejected
```

## Socratic Intake Prompts

1. What were you trying to do without opening docs?
2. Which command, screen, receipt, or output made you pause?
3. Which approval, audit, cost, rollback, or state fact did you need earlier?
4. What would have made ask, approve, verify, or undo obvious?
5. Is this friction one-off, repeated, or caused by a hidden config/source?

## Expanded Entry Format

```markdown
### YYYY-MM-DD - Short title

- **Type:** evidence | hypothesis
- **Source:** owner real use | [hypothesis: source, date]
- **Context:** command/surface/run phase, if known
- **Run/receipt:** run ID, receipt link, audit path, or `n/a`
- **Attempted:** What the owner or source tried to do.
- **Expected:** What should have happened.
- **Actual:** What happened instead.
- **Harness impact:** approval | audit | rollback | cost | receipt | state | validation | ergonomics
- **Status:** open | closed | rejected
- **Closure evidence:** commit/test/doc link; `n/a` only while open or rejected
- **Promoted to:** ticket/acceptance-gap link; `n/a` only before promotion or when rejected
```

## Owner Evidence Entries

### 2026-06-22 - Governance vocabulary on daily path (F2)

- **Type:** evidence
- **Source:** owner real use
- **Context:** daily ask/approve/undo; `teaagent daily`, receipts, cockpit-adjacent surfaces
- **Run/receipt:** n/a
- **Attempted:** Complete a normal coding task without mentally mapping internal product nouns.
- **Expected:** Plain-language ask/approve/undo with progressive disclosure only when needed.
- **Actual:** Internal words (tenant, envelope, trust tier, cockpit) still appear on the daily path before I get a plain answer.
- **Harness impact:** ergonomics
- **Status:** closed
- **Closure evidence:** cli_output.py TTY defaults; human_output soften_operator_copy; tui/core.py labels
- **Promoted to:** `tests/test_friction_ux_fixes.py::test_soften_operator_copy` (regression guard; fixed inline, no ticket)

### 2026-06-22 - JSON before plain-language receipt (F3)

- **Type:** evidence
- **Source:** owner real use
- **Context:** post-run review; `teaagent daily`, run show, approvals
- **Run/receipt:** n/a
- **Attempted:** Read what happened and what to do next in one glance after a run.
- **Expected:** Plain-language first line; structured JSON only behind `--json` or an explicit flag.
- **Actual:** JSON blobs are the default on several surfaces; I must remember `--human` or parse JSON to get the actionable sentence.
- **Harness impact:** receipt
- **Status:** closed
- **Closure evidence:** ergonomics/cli_output.py; agent run/daily/approval/cockpit TTY human default; --json escape hatch
- **Promoted to:** `tests/test_friction_ux_fixes.py::test_wants_human_cli_tty_default` (regression guard; fixed inline, no ticket)

### 2026-06-22 - TUI advertises unimplemented commands (F6)

- **Type:** evidence
- **Source:** owner real use
- **Context:** `teaagent tui` / `teaagent chat`; HELP and live state panel
- **Run/receipt:** n/a
- **Attempted:** Use documented TUI commands (`conflict`, `parallel`, or shortcuts `o/t/n/p/a`) for merge/conflict workflow.
- **Expected:** Commands behave as HELP describes (start branches, resolve conflicts).
- **Actual:** Got `not_available` or option-store-only behavior; help panel still instructs commands that are stubs.
- **Harness impact:** ergonomics
- **Status:** closed
- **Closure evidence:** ADR-0038 HELP_TEXT + tests/tui/test_tui_command_truth.py; tui/core.py Run status labels
- **Promoted to:** `tests/tui/test_tui_command_truth.py` (regression guard; U-P0-2 / ADR-0038)

### 2026-06-22 - agent run errors without hints (F7)

- **Type:** evidence
- **Source:** owner real use
- **Context:** non-interactive `teaagent agent run`; task resolution, plan-gate, background paths
- **Run/receipt:** n/a
- **Attempted:** Recover from a failed or blocked `agent run` using CLI error output alone.
- **Expected:** Same `format_error_block` treatment as other CLI paths (`-> hint`, categorized denial).
- **Actual:** Raw `{'status':'error',...}` JSON without the colored hint path; slower recovery than on `chat` or formatted harness errors.
- **Harness impact:** ergonomics
- **Status:** closed
- **Closure evidence:** run.py parallel/run-id guards; config.py plan gate; tests/test_cli_run_error_formatting.py
- **Promoted to:** `tests/test_cli_run_error_formatting.py` (regression guard; U-P1-2)

### 2026-06-22 - Shell inspect allowlist surprise (F8)

- **Type:** evidence
- **Source:** owner real use
- **Context:** agent-driven shell during coding runs; `workspace_run_shell_inspect` vs mutate tools
- **Run/receipt:** n/a
- **Attempted:** Let the agent inspect output with normal shell idioms (pipe, `cat`, compound commands).
- **Expected:** Tool choice and failure mode would be obvious before burning iterations.
- **Actual:** Inspect allowlist rejected common idioms; recovery turns and downstream errors obscured the root cause.
- **Harness impact:** validation
- **Status:** closed
- **Closure evidence:** workspace_tools/_shell.py + _files.py tool description; tests/test_friction_ux_fixes.py
- **Promoted to:** `tests/test_friction_ux_fixes.py::test_shell_inspect_error_lists_allowed_commands` (regression guard; fixed inline, no ticket)

## Owner Capture Batch (DR-001 debate)

> **Not evidence.** Answer yes/no (+ surface) from real use; promote each "yes"
> to `## Owner Evidence Entries` using the Quick Capture template above.
> Derived from [dr-006-owner-decision](../strategy/dr-006-owner-decision-2026-06-22.md) debate.

| # | Confirm prompt | If yes → harness impact |
| --- | --- | --- |
| F1 | Config/read-only source still confusing despite `teaagent doctor config`? | ergonomics |
| F2 | Internal words (tenant/envelope/cockpit) on daily output? | ergonomics |
| F3 | JSON before plain answer on run/daily/approvals? | receipt |
| F4 | Approval via hunting `call_id` in `approvals pending` JSON? | approval |
| F5 | Ever tried `agent run --background <run_id>` expecting resume? | state |
| F6 | TUI help advertised `conflict`/`parallel` but got not-available? | ergonomics |
| F7 | `agent run` errors as raw JSON without `-> hint`? | ergonomics |
| F8 | Shell inspect allowlist surprise (pipe/`cat`/recovery spiral)? | validation |

**Target:** any five "yes" answers → five evidence entries (TASK-007 / DR-001 7b).

**Owner batch result (2026-06-22):** F2, F3, F6, F7, F8 confirmed → five evidence entries recorded above. F1/F4/F5 not confirmed.

### 2026-06-22 - Approval via call_id hunting [hypothesis]

- **Type:** hypothesis
- **Source:** [hypothesis: UX survey 2026-06-06 + retrospective 04-ux-usability, 2026-06-22]
- **One-line capture:** Blocked runs may require `approvals pending` → extract `call_id` → `approve` instead of inline "approve this edit."
- **Status:** open
- **Promoted to:** n/a

### 2026-06-22 - agent run JSON errors without hints [hypothesis]

- **Type:** hypothesis
- **Source:** [hypothesis: retrospective 04-ux-usability.md, 2026-06-22]
- **One-line capture:** `agent run` task/plan/background failures may bypass `format_error_block` hints.
- **Status:** open
- **Closure evidence:** Owner evidence F7 (2026-06-22)
- **Promoted to:** [Owner evidence: agent run errors without hints](#2026-06-22---agent-run-errors-without-hints-f7)

### 2026-06-22 - Run id passed as task [hypothesis]

- **Type:** hypothesis
- **Source:** [hypothesis: owner capture batch (F5), 2026-06-22]
- **One-line capture:** `agent run <run_id>` or `--background <run_id>` may be confused with task text; owner did not confirm in the capture batch (F5 not confirmed).
- **Status:** open
- **Closure evidence:** n/a (guard implemented defensively: `run.py` run-id + background guards, `tests/test_cli_run_error_formatting.py`); awaiting owner validation
- **Promoted to:** n/a

## Competitor-Derived Hypotheses

### 2026-06-22 - Governance vocabulary on daily path

- **Type:** hypothesis
- **Source:** [hypothesis: harness-first direction §5.2 + intent debate, 2026-06-22]
- **One-line capture:** Daily ask/approve/undo path may still surface tenant/envelope/cockpit nouns instead of plain-language receipts.
- **Status:** open
- **Closure evidence:** Owner evidence F2 (2026-06-22)
- **Promoted to:** [Owner evidence: Governance vocabulary on daily path (F2)](#2026-06-22---governance-vocabulary-on-daily-path-f2)

### 2026-06-22 - Receipts need plain-language first line

- **Type:** hypothesis
- **Source:** [hypothesis: harness-first direction §5.2, 2026-06-22]
- **One-line capture:** Run receipts may bury the actionable answer behind JSON unless `--json` is explicit.
- **Status:** open
- **Closure evidence:** Owner evidence F3 (2026-06-22)
- **Promoted to:** [Owner evidence: JSON before plain-language receipt (F3)](#2026-06-22---json-before-plain-language-receipt-f3)

### 2026-06-22 - Config source confusion ("why is it read-only")

- **Type:** hypothesis
- **Source:** [hypothesis: harness-first direction §5.2 / V8 lesson, 2026-06-22]
- **One-line capture:** Effective permission mode may be unclear without `teaagent doctor config` provenance view.
- **Status:** open
- **Closure evidence:** TASK-005 / `teaagent doctor config` (2026-06-14); owner must still confirm in real use
- **Promoted to:** n/a

### 2026-06-22 - Epistemology gap (friction log vs competitor backlog)

- **Type:** hypothesis
- **Source:** [hypothesis: direction-review-agenda-2026-06-22, 2026-06-22]
- **One-line capture:** Backlog may still prioritize competitive-survey items while owner friction log has zero evidence entries.
- **Status:** open
- **Closure evidence:** DR-006 T1 Option B+ ratified 2026-06-22
- **Promoted to:** [DR-006 Owner Decision](../strategy/dr-006-owner-decision-2026-06-22.md)

Add further hypotheses only after a dated source is captured through the
[Signal-to-Acceptance-Gap Process](../processes/signal-to-acceptance-gap.md).

## Related Rules

- [Harness-First Direction](../strategy/harness-first-direction-2026-06-13.md)
- [Signal-to-Acceptance-Gap Process](../processes/signal-to-acceptance-gap.md)
- [Evidence to Principle Policy](../governance/evidence-to-principle-policy.md)
