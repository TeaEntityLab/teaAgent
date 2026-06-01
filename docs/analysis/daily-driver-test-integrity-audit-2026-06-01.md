# Daily-Driver Test-Integrity Audit
# 2026-06-01

**Why.** CG-16 found a *passing* test that masks a P1 bug (CG-11): it injects the state
it claims to verify. 104 TUI tests pass while `/cost` is broken in a live session. A
green suite that over-states correctness is worse than a known gap — it actively
prevents discovery. This doc names the anti-pattern, lists the grounded instances, and
gives a rule to keep it from recurring.

**Scope.** `tests/test_tui.py` cost/budget/undo tests, cross-checked against the runtime
paths in `teaagent/tui/__init__.py`.

---

## 1. The anti-pattern: "inject-the-state-you-assert"

A test sets a private field directly, then asserts the *display* of that field. It
verifies formatting but **skips the production code path that is supposed to set the
field**. If that path is broken (or absent), the test still passes.

```python
# tests/test_tui.py:1140  — masks CG-11
def test_tui_cost_shows_session_cost(self):
    tui._session_cost_cents = 123.0   # ← injected; the bug is that NOTHING sets this
    tui._handle_cost()
    self.assertIn('$1.23', ...)       # ← asserts formatting, not accumulation
```

The real bug: `_run_agent_task` never does `_session_cost_cents += result.cost_cents`
(CG-11). No test runs a task and asserts the counter moved — so the gap is invisible.

## 2. Grounded instances (this file)

| Test (line) | Field injected | Asserts | Verdict |
|---|---|---|---|
| `test_tui_cost_shows_session_cost` (`:1140`) | `_session_cost_cents = 123.0` | display `$1.23` | **Masking** — no accumulation test exists (CG-16) |
| budget display test (`:1132`) | `_session_cost_cents = 50.0` | budget text | Masking-adjacent — same field, never accumulated |
| budget test (`:1087`) | `_session_cost_cents = 50.0` | remaining budget | Masking-adjacent |
| effort tests (`:1047,1057,1064,1074`) | assert `_runtime_max_cost_cents` **after a handler ran** | value set by `/effort` | **Legitimate** — exercises the setter, asserts the effect |

The distinction matters: asserting a field *after the handler that sets it ran* (effort
tests) is correct. Asserting a display *of a hand-set field* (cost tests) is the
anti-pattern, **when no other test covers the setter**.

## 2b. Second instance: a parity test that never touches the surface it names (CG-17)

`test_chat_surface_parity` (`tests/test_cli_chat.py:483-552`) has the docstring *"CLI and
TUI surfaces use the same controller (CG-05)"* but constructs **two
`ChatSessionController` instances** and runs `execute_task` on both. It never imports or
instantiates `TeaAgentTUI`. So it verifies the controller is deterministic against itself
— not that the TUI *uses* the controller (it doesn't; CG-12). The test passes precisely
because it avoids the divergent code. This is the same anti-pattern as CG-16 at the
integration level: **the name claims surface parity; the body tests a single class twice.**

A real parity test must drive the actual surfaces: build a `TeaAgentTUI`, run a task
through `_run_agent_task`, run the same task through the REPL path, and assert equal
status/cost-delta/undo. Until then, "parity" is asserted but unproven.

## 3. The rule

> For every piece of state shown to the user, at least one test must drive the
> **production path that produces it** and assert the value — not inject it. Injection
> tests are allowed *only* for pure formatting, and only *alongside* a path test.

Concretely for cost: keep `test_tui_cost_display_formatting` (injection, formatting
only) **and** add `test_tui_session_cost_accumulates` (runs a stub-cost task, asserts the
counter rose). The second is the one that would have caught CG-11.

## 4. Cheap guardrail (optional)

A reviewer checklist line — *"Does this test set the field it asserts? If so, where is
the test that the field gets set in production?"* — catches the pattern in review
without tooling. A heavier option: a lint that flags `self._<field> = …` followed by an
assertion on the same field within a test body, requiring a paired path-test by naming
convention. Recommend the checklist now; defer the lint (low ROI vs the migration work).

## 5. What to re-audit after TICKET-12

Once the TUI uses the controller, `session_cost_cents` lives in `SessionState`. Re-point
the accumulation test at the controller and assert REPL/TUI parity
(`test_chat_surface_parity`) — that single test then covers both surfaces' accumulation,
retiring the per-surface masking risk.

## Cross-references
- Finding: `daily-driver-third-pass-postfix-audit-2026-06-01.md` (CG-16).
- Fix tickets: TICKET-14 (this), TICKET-12 (the bug it masks), execution sheets doc.
- Prior execution risk this realizes: ER-5 ("fixes pass tests but break a real session").
