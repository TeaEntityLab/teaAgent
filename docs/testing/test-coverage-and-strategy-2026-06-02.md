# Test Coverage & Testing Strategy
# teaagent — 2026-06-02

**How to use this document.**
Section 1 is the raw baseline (pytest-cov output). Section 2 is the gap analysis — what is
missing and why it matters. Section 3 is the anti-pattern audit. Section 4 is the
integration coverage map. Section 5 is the error-path audit. Section 6 is the strategy
recommendation. Section 7 is the regression specification: one test shape per defeat
scenario, with enough code sketch to implement without re-reading source.

---

## Table of Contents

1. [Coverage Baseline](#1-coverage-baseline)
2. [Gap Analysis — Uncovered Critical Paths](#2-gap-analysis)
3. [Test Anti-Pattern Audit](#3-test-anti-pattern-audit)
4. [Integration Test Coverage Map](#4-integration-test-coverage-map)
5. [Error Path Audit](#5-error-path-audit)
6. [Recommended Test Strategy](#6-recommended-test-strategy)
7. [Regression Suite Specification (13 Defeat Scenarios)](#7-regression-suite-specification)

---

## 1. Coverage Baseline

**Command run:** `pytest --cov=teaagent --cov-report=term-missing -q --tb=no --ignore=tests/acceptance --ignore=tests/e2e`

**Run date:** 2026-06-02
**Outcome:** 2,834 passed, 49 skipped, 2 failed (`test_mcp_trust.py::test_mcp_trust_policy_serialization`, `test_mcp_trust.py::test_mcp_trust_policy_persistence`)
**Acceptance and e2e suites excluded** (they require live infra; 3,320 total tests when included)

### 1.1 Aggregate

| Metric | Value |
|--------|-------|
| Statements | 33,201 |
| Missed | 9,229 |
| **Overall coverage** | **72%** |

### 1.2 Module Coverage — Full Table (sorted by %)

Modules at ≥ 90% omitted from detail rows unless they contain a known defeat-scenario path.

#### Red (< 30%)

| Module | Stmts | Missed | Cover | Notes |
|--------|------:|------:|------:|-------|
| `cli/__main__.py` | 2 | 2 | 0% | Entry point only; trivially untested |
| `cli/_handlers/_chat.py` | 689 | 636 | **8%** | PRIMARY user interface — REPL + TUI entry. **Critical.** |
| `cli/_handlers/_plugin.py` | 97 | 89 | 8% | Plugin install/remove commands |
| `cli/_handlers/_gateway.py` | 56 | 48 | 14% | Messaging gateway handler |
| `cli/_handlers/_mcp_trust.py` | 70 | 58 | 17% | MCP trust policy CLI |
| `cli/_handlers/_env.py` | 50 | 39 | 22% | Env var management |
| `plan.py` | 175 | 123 | 30% | Plan parsing + execution |

#### Amber (30–59%)

| Module | Stmts | Missed | Cover | Notes |
|--------|------:|------:|------:|-------|
| `sigstore_signer.py` | 88 | 55 | 38% | Supply-chain signing |
| `cli/_handlers/_memory.py` | 120 | 73 | 39% | Memory catalog CLI |
| `cli/_handlers/_audit.py` | 116 | 69 | 41% | Audit viewer/export CLI |
| `cli/_handlers/_audit.py` | 116 | 69 | 41% | Audit viewer/export CLI |
| `backend_registry.py` | 90 | 50 | 44% | Backend adapter registration |
| `cli/_handlers/_approval_subagents.py` | 67 | 37 | 45% | Sub-agent approval CLI |
| `cli/_handlers/_cloud.py` | 55 | 28 | 49% | Cloud task commands |
| `cli/_handlers/_marketplace.py` | 42 | 23 | 45% | Skill marketplace |
| `cli/_handlers/_experiment.py` | 103 | 58 | 44% | A/B experiment commands |
| `cli/_handlers/_agent.py` | 1354 | 734 | **46%** | Agent subcommands — **resume, background run, interactive-review.** Critical. |
| `subagents/_team_orchestrator.py` | 126 | 60 | 52% | Multi-agent team coordination |
| `skill_candidates.py` | 172 | 81 | 53% | Skill discovery |
| `cli/_handlers/_consensus.py` | 228 | 105 | 54% | Consensus voting CLI |
| `skill_executor.py` | 148 | 65 | 56% | Skill execution runtime |
| `subagents/_approval_queue.py` | 457 | 191 | 58% | Sub-agent approval queue — large, security-relevant |

#### Yellow (60–74%)

| Module | Stmts | Missed | Cover | Notes |
|--------|------:|------:|------:|-------|
| `agent_factory.py` | 121 | 49 | 60% | Agent construction |
| `cli/_handlers/_misc.py` | 245 | 96 | 61% | Miscellaneous CLI commands |
| `subagents/_review.py` | 108 | 40 | 63% | Sub-agent review logic |
| `sandbox/_git_branch.py` | 374 | 126 | 66% | Git-worktree sandbox — **undo and isolation paths** |
| `cli/_handlers/_ergonomics.py` | 581 | 195 | 66% | Ergonomics / UX commands |
| `runner/_auto_mode_manager.py` | 33 | 11 | 67% | Auto-mode manager |
| `security_env.py` | 19 | 6 | 68% | Security env config |
| `policy.py` | 204 | 65 | 68% | Policy evaluation — access control |
| `selftest.py` | 43 | 12 | 72% | Self-test harness |
| `session.py` | 124 | 37 | 70% | Session lifecycle |
| `run_undo.py` | 170 | 37 | 78% | Undo journal — **surgical undo paths** |
| `approval_manager.py` | 339 | 89 | 74% | Approval lifecycle — **DS-12 empty-path paths** |

#### Green-but-notable (≥ 75% with defeat scenario exposure)

| Module | Cover | Notes |
|--------|------:|-------|
| `chat_session_controller.py` | 80% | Lines 154-159 (persistence error swallowing — DS-03) are uncovered |
| `tui/__init__.py` | ~88% (est.) | `_run_agent_task` accumulation path now covered; undo handler not verified against journal |
| `runner/_core.py` | 91% | Budget-cap check (`max_estimated_cost_cents <= 0`) at :142 — DS-13 |
| `run_store.py` | 97% | Essentially full |

---

## 2. Gap Analysis

### 2.1 The CLI Handler Desert

`cli/_handlers/_chat.py` has **8% coverage on 689 lines**. This single file is the entry
point for every interactive session (`teaagent chat`, REPL, TUI bootstrap). What the 92%
miss includes:

- `chat_command()` — the dispatcher that resolves `args.task` and calls `run_tui`
- `run_chat_repl()` — the REPL loop including `/undo`, `/cost`, `/background` handlers
- All TUI lifecycle: `run_tui()`, permission-mode wiring, model selection
- Session suspension path: `suspend_to_background()`, the JSON serialiser
- Every REPL command handler (`_handle_undo`, `_handle_cost`, `_handle_reset`, …)

The test file `tests/test_cli_chat.py` (49 tests) tests isolated functions (suspend
serialisation, parity via controllers, cost tracking) but almost none drive through
the public entry points. The gap is structural: tests mock `run_chat_agent` before
it reaches the handler, so the handler code never runs.

**Risk:** A regression in any REPL command handler will be invisible to CI.

---

### 2.2 The Agent Handler Blind Spot

`cli/_handlers/_agent.py` has **46% coverage on 1,354 lines** (734 lines missed). The
covered half is primarily `agent_run_task` happy path and subcommand parsing. The uncovered
half includes:

- `agent_resume_command` (lines 192–211, 235–247) — DS-08: always errors
- `_start_background_run` (lines 145–166) — DS-09: silently runs UUID as task
- Interactive-review with suspension context loading (lines 714–913)
- The full `_load_suspension_data` path (lines 1057–1087)
- All background-run status poll / attach commands

**Risk:** The two highest-impact resume/background bugs (DS-08, DS-09) live in dead zones. Any fix to those paths has no CI safety net.

---

### 2.3 Approval Manager Security Gap

`approval_manager.py` at 74% has its missing 89 lines concentrated in:

- Lines 294–313: path-scope rule creation — the exact path where DS-12 (empty-path → global grant) lives
- Lines 326–376: approval matching with glob evaluation
- Lines 405–481: session-scope grant lifecycle

These are the security-critical paths. A test that verifies an empty-path approval does
NOT create a wildcard grant does not exist anywhere in the test suite (confirmed by grep).

---

### 2.4 Undo and Git-Sandbox Fragility

`run_undo.py` at 78% and `sandbox/_git_branch.py` at 66% are both in the undo-and-isolation
surface. The uncovered lines in `run_undo.py` (126, 152, 155, 178–179, 192, 200–201,
206, 212–213, 217–218, 223, 230–234, 246–253, 275–288) include:

- Partial-restore failure paths (some files succeeded, others failed)
- UndoJournal with no entries
- Restore from non-existent path

`sandbox/_git_branch.py` misses lines 371–420 and 707–729 — the worktree-conflict
resolution and stash-conflict paths that are exercised during TUI undo (DS-05).

---

### 2.5 Controller Persistence Error Paths

`chat_session_controller.py` lines 154–159 are uncovered. These are inside the
`except (AttributeError, TypeError): pass` guard (DS-03 / CG-13). No test deliberately
triggers a persistence error and verifies the user still sees a meaningful outcome.
The swallowing is also untested — if the except is removed, existing tests don't fail.

---

## 3. Test Anti-Pattern Audit

### AP-1 — State Injection Masking (CG-16 pattern)

**Location:** `tests/test_tui.py:1141–1148` (`test_tui_cost_shows_session_cost`)

```python
tui._session_cost_cents = 123.0   # ← injects final state, bypasses accumulation
tui._handle_cost()
self.assertIn('$1.23', ' '.join(output))
```

**What it proves:** The formatter converts cents to dollars correctly.
**What it does NOT prove:** That `_run_agent_task` ever increments `_session_cost_cents`.

A companion regression test (`test_tui_run_agent_task_accumulates_cost`) was added in
TICKET-14 and correctly drives the accumulation path. **However, the masking test remains**
and its comment now says "see accumulation test." The masking test is harmless post-fix
but exemplifies the anti-pattern. Future contributors can't distinguish "tests the formatter"
from "tests the accumulation" by looking at test names.

**Rule:** Never inject internal state to test a display path. Test display by completing the
full production path and asserting the displayed value. Keep formatter tests only for edge
cases the full path cannot easily exercise (currency symbols, overflow formatting, etc.).

---

### AP-2 — Hollow Parity Test (CG-17 pattern)

**Location:** `tests/test_cli_chat.py:482–563` (`test_chat_surface_parity`)

```python
cli_controller = ChatSessionController(root=tmpdir, ...)
tui_controller = ChatSessionController(root=tmpdir, ...)
# ... both execute via controller.execute_task()
assert cli_output == tui_output   # tests controller == controller, not TUI == REPL
```

**What it proves:** Two `ChatSessionController` instances produce identical output for the
same task.

**What it does NOT prove:** That `TeaAgentTUI._run_agent_task` (which calls `run_chat_agent`
directly, bypassing the controller) produces the same result as the REPL.

The test never imports or instantiates `TeaAgentTUI`. It cannot catch CG-12 (TUI not using
controller) because it never exercises the TUI code path.

**Rule:** A parity test must construct and exercise both surfaces via their public entry
points. If the TUI cannot be easily instantiated in tests, that is itself a design signal.

---

### AP-3 — Mock-Before-Handler Pattern

**Pattern:** Tests in `test_cli_chat.py` and `test_tui.py` patch `run_chat_agent` at the
module level before the handler function runs, meaning the handler's argument routing,
validation, and branching logic is never tested.

**Example:**
```python
# tests/test_cli_chat.py (pattern repeated ~20 times)
with patch('teaagent.chat_session_controller.run_chat_agent') as mock:
    mock.return_value = success_result
    controller.execute_task('task', config)
    assert ...  # only asserts on controller output, never on handler routing
```

**What this misses:** Any bug in how the handler assembles `config`, routes `args.task`,
or handles edge cases in argument parsing will be invisible.

---

### AP-4 — Exception-Swallowing Without Coverage

**Location:** `teaagent/chat_session_controller.py:143–159`

```python
try:
    if audit and hasattr(audit, 'path') and audit.path:
        store = RunStore(self.root)
        store.logger_for_result(result, audit)
except (AttributeError, TypeError):
    pass   # ← never executed in any test
```

Coverage shows lines 154–159 (the second `except` block) are never hit. This means CI
cannot distinguish "the except block is correct" from "the except block has a bug."
More importantly, the production failure mode (persistence failure silently swallowed)
has no test asserting that the user at least sees... anything. The test suite is green
whether or not persistence errors are swallowed or re-raised.

---

### AP-5 — Suspension Tests That Don't Resume

`test_cli_chat.py` has four `test_suspend_to_background_*` tests (lines 345, 948, 968,
1020). All test the write-side of suspension (JSON written, output printed). None test the
read-side: calling `teaagent resume <id>` after a REPL suspension. This is a write-only
test pattern — it verifies that data is persisted but never that it can be loaded.

---

### AP-6 — Acceptance Tests That Don't Assert Behaviour

`tests/acceptance/` contains 100+ files. A sample inspection shows many follow the pattern:

```python
def test_some_feature_flow():
    # no assertions; just imports and maybe a mock call
    assert True
```

Some acceptance tests exist as placeholders — they confirm the import path is valid but
assert nothing about behavior. These inflate the test count without providing coverage
signal. See `test_docs_acceptance_count_accuracy.py` which tests that the right number of
acceptance tests exist, not that they pass.

---

## 4. Integration Test Coverage Map

### 4.1 Tested Subsystem Interactions

| Interaction | Test location | Quality |
|-------------|--------------|---------|
| `ChatSessionController` ↔ `RunStore` | `test_cli_chat.py:300–344` | Medium — mocked store |
| `ChatSessionController` ↔ `UndoJournal` | `test_cli_chat.py:400–480` | Good — uses real journal |
| `TUI` ↔ `run_chat_agent` | `test_tui.py:1150–1220` | Good — real call path via mock agent |
| `AuditLogger` ↔ `RunStore` | `integration/test_audit_chain.py` | Good |
| `ApprovalManager` ↔ `permission mode` | `test_approval_async_from_sync.py` | Shallow |
| `Runner` ↔ `budget guard` | `test_budget.py`, `test_automation_run_budget.py` | Medium |
| `RunUndo` ↔ `git operations` | `integration/test_run_undo.py` | Medium |
| `SubagentApprovalQueue` ↔ `store` | `test_subagent_approval_queue_store.py` | Good |
| `sandbox/_git_branch` ↔ real git | `test_git_sandbox.py` | Medium — real git, happy path only |
| `REPL suspend` ↔ `resume command` | **NOT TESTED** | Missing |
| `TUI _run_agent_task` ↔ `controller` | **NOT TESTED** | Missing (DS-02 / CG-12) |
| `Approval empty-path` ↔ `permission scope` | **NOT TESTED** | Missing (DS-12) |
| `agent_resume_command` ↔ `RunStore` | **NOT TESTED** | Missing (DS-08) |
| `--background <id>` disambiguation | **NOT TESTED** | Missing (DS-09) |
| `cost_cap=0` ↔ `runner budget guard` | `test_automation_run_budget.py:117` | Shallow — no behavior assertion |

### 4.2 Integration Test Anti-Pattern: Mocked Infrastructure

`tests/integration/` tests frequently mock their storage backends:

```python
# integration/test_runner_cost_tracking.py (representative)
with patch('teaagent.run_store.RunStore') as mock_store:
    ...
```

This means "integration" tests are really unit tests with a wider import scope. The
`RunStore`, `AuditLogger`, and `UndoJournal` are the exact components that cause silent
failures in production (DS-03). A mocked store cannot detect a `TypeError` in JSON
serialisation.

**Recommendation:** At least one integration test per critical subsystem interaction
should use a real temp-directory-backed store, not a mock.

---

## 5. Error Path Audit

### 5.1 Tested error paths

| Path | Test | Verdict |
|------|------|---------|
| Runner: `max_estimated_cost_cents` exceeded | `test_budget.py` | Tested (happy path only — cap fires) |
| `UndoJournal.restore()` file-not-found | `test_run_undo.py` | Partially tested |
| `RunStore.task_for_run` raises `ValueError` | None found | **UNTESTED** |
| LLM adapter: auth failure | `test_llm.py` | Mocked — actual HTTP path not tested |
| `audit.record()` disk-full | `integration/test_disk_full_degradation.py` | Tested (good) |
| Approval denied: user callback | `test_approval_async_from_sync.py` | Tested |
| Sandbox worktree conflict | `test_git_sandbox.py` | Happy path only |

### 5.2 Untested error paths (high risk)

| Path | Module | Defeat scenario |
|------|--------|-----------------|
| Persistence failure in `logger_for_result` | `chat_session_controller.py:143–150` | DS-03 |
| Persistence failure in `undo_journal.save_to` | `chat_session_controller.py:153–159` | DS-03 |
| `store.task_for_run()` raises `ValueError` for REPL suspension id | `_agent.py:217` | DS-08 |
| `agent run --background <uuid>` treats UUID as task string | `_agent.py:145–146` | DS-09 |
| Empty path in path-scoped approval rule creation | `approval_manager.py:294–313` | DS-12 |
| `cost_cap == 0` treated as unlimited in runner | `runner/_core.py:142` | DS-13 |
| TUI `/undo` invokes `_restore_checkpoint` instead of `UndoJournal` | `tui/__init__.py:641` | DS-05 |
| Observations not rehydrated on `interactive-review` | `_agent.py:239–244` | DS-10 |

### 5.3 Only Happy Paths

The following critical subsystems have tests only for the success case:

- **Budget warnings** (`test_budget_warnings.py`) — no test for "warning fires but agent continues anyway"
- **Sandbox isolation** (`test_sandbox_hardening.py`) — no test for "subagent escapes isolation"
- **Context compaction** (`test_context_auto_compaction.py`) — no test for "compaction fires mid-task with active undo journal"

---

## 6. Recommended Test Strategy

### 6.1 Test Pyramid Assessment

Current state is an **inverted pyramid**:

```
         ┌─────────────────────────────────┐
         │  Unit tests (mocked)            │  ← Most tests live here
         │  ~2,500 tests, mostly mocked    │
         ├─────────────────────────────────┤
         │  Integration (real storage)     │  ← Thin and inconsistent
         │  ~200 tests, mixed quality      │
         ├─────────────────────────────────┤
         │  E2E / Acceptance               │  ← Mostly placeholder
         │  ~100 tests, many empty         │
         └─────────────────────────────────┘
```

Target pyramid for a CLI agent tool:

```
         ┌──────────────────────────────────┐
         │  E2E / acceptance (real infra)   │  ← Small, expensive, high value
         │  ~30 critical user flows         │
         ├──────────────────────────────────┤
         │  Integration (real storage)      │  ← Dominant tier for a stateful tool
         │  ~300 tests, no mocked stores    │
         ├──────────────────────────────────┤
         │  Unit (pure functions)           │  ← Only for pure logic
         │  ~500 tests, no IO mocked        │
         └──────────────────────────────────┘
```

**Why integration-dominant?** The bugs that bite users (DS-01 through DS-13) are all
integration failures — a value written to one object, never read by another. Unit tests
cannot catch them; only tests that exercise the write-read cycle can.

---

### 6.2 Immediate Priorities (P0 — Block CI)

These gaps have confirmed live bugs or security issues with no CI detector:

| Priority | Module | What to add |
|----------|--------|-------------|
| P0 | `cli/_handlers/_chat.py` | Drive `chat_command()` with `args.task='task'`; assert TUI receives it |
| P0 | `cli/_handlers/_agent.py` | Test `agent_resume_command` with a REPL-originated suspension id |
| P0 | `approval_manager.py` | Test that empty-path approval raises `ValueError` or defaults to cwd |
| P0 | `chat_session_controller.py` | Test persistence failure → user still sees task result |

### 6.3 High-Priority Additions (P1 — Address within 1 sprint)

| Priority | What | Why |
|----------|------|-----|
| P1 | Rewrite `test_chat_surface_parity` to instantiate `TeaAgentTUI` | CG-17: hollow parity |
| P1 | Test `cost_cap=0` at `runner._core` level | DS-13: user sets 0, gets unlimited |
| P1 | Test TUI `/undo` consumes `UndoJournal` (not `_restore_checkpoint`) | DS-05 |
| P1 | Test `agent run --background <uuid>` warns/errors | DS-09 |
| P1 | Cover `sandbox/_git_branch.py` conflict paths | DS-05 amplifier |

### 6.4 Technical Debt (P2 — Address within next quarter)

- Replace mocked-store integration tests with real temp-directory stores
- Delete or rename acceptance test placeholders that assert nothing
- Add `@pytest.mark.regression` markers to defeat-scenario tests
- Add `--fail-under=75` to CI coverage gate (currently 72%; raise 2% per sprint)

---

### 6.5 Coverage Gate Recommendation

```toml
# pyproject.toml
[tool.pytest.ini_options]
addopts = "--cov=teaagent --cov-fail-under=75"
```

Start at 75% (just above current 72%), raise by 2% each sprint. Pair with per-file
minimums for the five highest-risk modules:

```
# .coveragerc
[report]
fail_under = 75

[paths]
critical =
    teaagent/cli/_handlers/_chat.py
    teaagent/cli/_handlers/_agent.py
    teaagent/approval_manager.py
    teaagent/chat_session_controller.py
    teaagent/run_undo.py
```

Set per-file minimums at 40% for the critical set, raising 10% per sprint until 80%.

---

## 7. Regression Suite Specification

One test shape per defeat scenario. Code sketches use pytest conventions. Each test
must be decorated `@pytest.mark.regression` and placed in `tests/regression/`.

---

### DS-01 · CG-11 — TUI cost accumulation

**Status:** FIXED (commit `31df3ba`). Regression test `test_tui_run_agent_task_accumulates_cost` exists.
**Verify:** Run `pytest tests/test_tui.py::TUITests::test_tui_run_agent_task_accumulates_cost` — must pass.

```python
@pytest.mark.regression
def test_tui_session_cost_accumulates_across_tasks(tmp_path):
    """Cost must compound across multiple _run_agent_task calls (not reset each time)."""
    from teaagent.tui import TeaAgentTUI
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=lambda _: None)
    # Run task 1: cost 50¢
    with patch('teaagent.tui.run_chat_agent') as mock_run, \
         patch('teaagent.tui.RunStore'), patch('teaagent.tui.create_llm_adapter'):
        mock_run.return_value = _make_result(cost_cents=50.0)
        tui._run_agent_task('task 1', _make_config(tmp_path))
    # Run task 2: cost 75¢
    with patch('teaagent.tui.run_chat_agent') as mock_run, \
         patch('teaagent.tui.RunStore'), patch('teaagent.tui.create_llm_adapter'):
        mock_run.return_value = _make_result(cost_cents=75.0)
        tui._run_agent_task('task 2', _make_config(tmp_path))
    assert tui._session_cost_cents == 125.0, "Cost must compound, not reset"
```

---

### DS-02 · CG-12 — TUI must use ChatSessionController

**Status:** OPEN. No regression test.

```python
@pytest.mark.regression
def test_tui_run_task_uses_session_controller_not_run_chat_agent_directly(tmp_path):
    """TeaAgentTUI._run_agent_task must delegate to ChatSessionController.execute_task,
    not call run_chat_agent directly. This guards CG-12.
    """
    from teaagent.tui import TeaAgentTUI
    from teaagent.chat_session_controller import ChatSessionController
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=lambda _: None)
    with patch.object(
        ChatSessionController, 'execute_task', return_value=MagicMock(cost_cents=10.0)
    ) as mock_execute, \
    patch('teaagent.tui.run_chat_agent') as mock_direct:
        tui._run_agent_task('task', _make_config(tmp_path))
    mock_execute.assert_called_once()
    mock_direct.assert_not_called(), "TUI must not call run_chat_agent directly"
```

---

### DS-03 · CG-13 — Controller must not swallow real persistence errors

**Status:** OPEN (lines 143–159 not covered).

```python
@pytest.mark.regression
def test_controller_persistence_error_propagates_or_warns(tmp_path):
    """A real AttributeError from logger_for_result must not be silently swallowed.
    User must see either an error message or the except must be narrowed to test-only mocks.
    This test will fail as long as CG-13 is open.
    """
    from teaagent.chat_session_controller import ChatSessionController, SessionState
    output = []
    ctrl = ChatSessionController(root=str(tmp_path), output_fn=output.append,
                                  session_state=SessionState())
    # Simulate a real AttributeError from the store (not from a mock)
    real_attr_error_store = object()  # has no logger_for_result at all

    with patch('teaagent.chat_session_controller.RunStore', return_value=real_attr_error_store), \
         patch('teaagent.chat_session_controller.run_chat_agent',
               return_value=_make_run_result()):
        ctrl.execute_task('task', _make_config(tmp_path))

    # Either the error propagated (test passes by not crashing) OR
    # the user received a warning message — silent swallow is the failure.
    # Current behaviour: silent swallow → this assertion fails → CG-13 confirmed open.
    assert any('error' in m.lower() or 'warn' in m.lower() for m in output), \
        "Persistence error must produce visible output, not be silently swallowed (CG-13)"
```

---

### DS-04 · CG-14 — Stale audit_trail field in suspension JSON

**Status:** OPEN (cleanup).

```python
@pytest.mark.regression
def test_suspension_json_has_no_audit_trail_field(tmp_path):
    """suspension-{id}.json must NOT contain an 'audit_trail' key.
    That field is a stale pre-CG-10 remnant that misleads forensic analysis.
    """
    from teaagent.cli._handlers._chat import suspend_to_background
    result_path = tmp_path / 'suspension-test.json'
    with patch('teaagent.cli._handlers._chat.uuid4', return_value='test-id'):
        suspend_to_background(observations=[], config=_make_config(tmp_path),
                               output_fn=lambda _: None)
    data = json.loads((tmp_path / '.teaagent' / 'suspension-test.json').read_text())
    assert 'audit_trail' not in data, "Stale audit_trail field must be removed (CG-14)"
```

---

### DS-05 · CG-15 — TUI /undo must use UndoJournal, not git-stash

**Status:** OPEN.

```python
@pytest.mark.regression
def test_tui_undo_uses_undo_journal_not_git_stash(tmp_path):
    """TeaAgentTUI._handle_undo must call UndoJournal.restore(), not _restore_checkpoint().
    git-stash pop is destructive and wipes manual edits (CG-15).
    """
    from teaagent.tui import TeaAgentTUI
    output = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    with patch.object(tui, '_restore_checkpoint') as mock_stash, \
         patch('teaagent.tui.RunStore') as mock_store_cls, \
         patch('teaagent.tui.UndoJournal') as mock_journal_cls:
        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store
        mock_store.latest_run_with_undo.return_value = 'run-1'
        mock_store.undo_path.return_value = tmp_path / 'undo.jsonl'
        (tmp_path / 'undo.jsonl').write_text('{}')
        mock_journal = MagicMock()
        mock_journal_cls.return_value = mock_journal
        mock_journal.restore.return_value = MagicMock(ok=True, restored=['f.py'], deleted=[])
        tui._handle_undo()
    mock_journal.restore.assert_called_once(), "TUI undo must call UndoJournal.restore"
    mock_stash.assert_not_called(), "TUI undo must NOT call _restore_checkpoint (git-stash)"
```

---

### DS-06 · CG-16 — Masking test must not be the only cost test

**Status:** MITIGATED (accumulation test added). Regression test exists.
**Note:** `test_tui_cost_shows_session_cost` is still a state-injection test. It should be
annotated clearly as a formatter-only test, not a cost-correctness test. No new regression
test needed; verify the accumulation test still passes.

---

### DS-07 · CG-17 — Parity test must instantiate TeaAgentTUI

**Status:** OPEN.

```python
@pytest.mark.regression
def test_repl_and_tui_produce_same_output_for_same_task(tmp_path):
    """REPL (via controller) and TUI (via TeaAgentTUI) must produce identical visible output
    for the same task. Guards CG-12: if TUI diverges from controller, this test catches it.
    """
    from teaagent.tui import TeaAgentTUI
    from teaagent.cli._handlers._chat import run_chat_repl
    repl_output, tui_output = [], []
    result = _make_run_result(cost_cents=10.0, answer='Test answer')

    # Drive REPL path
    with patch('teaagent.cli._handlers._chat.run_chat_agent', return_value=result), \
         patch('teaagent.cli._handlers._chat.RunStore'), \
         patch('teaagent.cli._handlers._chat.create_llm_adapter'):
        run_chat_repl(_make_config(tmp_path), initial_task='test task',
                      output_fn=repl_output.append)

    # Drive real TUI path — not a second controller
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=tui_output.append)
    with patch('teaagent.tui.run_chat_agent', return_value=result), \
         patch('teaagent.tui.RunStore'), patch('teaagent.tui.create_llm_adapter'):
        tui._run_agent_task('test task', _make_config(tmp_path))

    assert 'Test answer' in '\n'.join(repl_output)
    assert 'Test answer' in '\n'.join(tui_output)
    assert repl_output == tui_output, f"Surface parity failure:\nREPL: {repl_output}\nTUI: {tui_output}"
```

---

### DS-08 · AG-01 — `teaagent resume <repl-id>` must not error with opaque message

**Status:** OPEN. `agent_resume_command` is in the 54% uncovered portion of `_agent.py`.

```python
@pytest.mark.regression
def test_resume_repl_suspension_id_gives_useful_error(tmp_path):
    """teaagent resume <id> after REPL /background must give a useful message,
    not 'run has no run_started task'. DS-08.
    """
    import json
    from teaagent.cli._handlers._agent import agent_resume_command
    # Write a REPL-style suspension JSON (contains session_suspended, no run_started)
    suspension_id = 'test-suspension-123'
    suspension_file = tmp_path / '.teaagent' / f'suspension-{suspension_id}.json'
    suspension_file.parent.mkdir(parents=True, exist_ok=True)
    suspension_file.write_text(json.dumps({'event_type': 'session_suspended',
                                           'observations': [], 'config': {}}))
    output = []
    args = argparse.Namespace(run_id=suspension_id, root=str(tmp_path))
    with patch('teaagent.cli._handlers._agent.RunStore') as mock_store:
        mock_store.return_value.task_for_run.side_effect = ValueError('no run_started task')
        result = agent_resume_command(args, output_fn=output.append)
    # Must not silently succeed OR give opaque ValueError message
    joined = '\n'.join(output)
    assert 'run_started' not in joined, "Error must not expose internal event-schema details"
    assert any(kw in joined.lower() for kw in ('suspend', 'background', 'interactive-review')), \
        "Error must guide user toward the working command (interactive-review)"
```

---

### DS-09 · AG-02 — `agent run --background <uuid>` must not silently start wrong run

**Status:** OPEN. `_start_background_run` is in the uncovered portion of `_agent.py`.

```python
@pytest.mark.regression
def test_agent_run_background_with_uuid_task_warns_or_errors(tmp_path):
    """'teaagent agent run --background <uuid>' must not silently start a run whose
    task is the UUID string. DS-09.
    """
    import re
    from teaagent.cli._handlers._agent import agent_run_task
    uuid_task = 'a3f9c12b-dead-beef-cafe-123456789abc'
    output = []
    args = argparse.Namespace(task=uuid_task, background=True, root=str(tmp_path),
                              model=None, effort=None, max_cost=None)
    with patch('teaagent.cli._handlers._agent._start_background_run') as mock_bg:
        agent_run_task(args, output_fn=output.append)
    # Either: run was blocked with a warning, OR mock was not called
    joined = '\n'.join(output)
    if mock_bg.called:
        # If it ran, user must have been warned
        assert any(re.search(r'uuid|run.id|resume|suspend', m, re.I) for m in output), \
            "UUID-shaped task must produce a disambiguation warning (DS-09)"
    # Preferred: it should NOT start the run at all without confirmation
    assert not mock_bg.called or any('warn' in m.lower() for m in output)
```

---

### DS-10 · AG-03 — `interactive-review` must expose saved observations

**Status:** OPEN.

```python
@pytest.mark.regression
def test_interactive_review_loads_suspension_observations(tmp_path):
    """When teaagent agent interactive-review <id> is called after REPL suspension,
    the suspended observations must be available in the review context. DS-10.
    """
    import json
    from teaagent.cli._handlers._agent import agent_interactive_review
    observations = [{'task': 'refactor auth', 'result': 'done'}]
    suspension_id = 'review-test-456'
    suspension_file = tmp_path / '.teaagent' / f'suspension-{suspension_id}.json'
    suspension_file.parent.mkdir(parents=True, exist_ok=True)
    suspension_file.write_text(json.dumps({'observations': observations, 'config': {}}))
    loaded_context = {}
    def capture_context(ctx):
        loaded_context.update(ctx)
    with patch('teaagent.cli._handlers._agent._load_suspension_data',
               side_effect=lambda path: json.loads(path.read_text())) as mock_load, \
         patch('teaagent.cli._handlers._agent._run_interactive_review') as mock_review:
        mock_review.side_effect = lambda ctx, **kw: loaded_context.update(ctx)
        args = argparse.Namespace(run_id=suspension_id, root=str(tmp_path))
        agent_interactive_review(args)
    assert loaded_context.get('observations') == observations, \
        "interactive-review must rehydrate suspension observations (DS-10)"
```

---

### DS-11 · UXD-001 — Initial task must reach TUI

**Status:** FIXED (commit `47710d9`). Regression test should exist in `test_cli_chat.py`.

```python
@pytest.mark.regression
def test_chat_command_passes_initial_task_to_tui(tmp_path):
    """teaagent chat 'my task' must pass 'my task' to run_tui as initial_task.
    Guards UXD-001 / TASK-DD2-001.
    """
    from teaagent.cli._handlers._chat import chat_command
    import argparse
    received_task = []
    args = argparse.Namespace(task='my task', root=str(tmp_path), model=None,
                               effort=None, max_cost=None, mode=None)
    with patch('teaagent.cli._handlers._chat.run_tui') as mock_tui:
        mock_tui.return_value = 0
        chat_command(args)
    call_kwargs = mock_tui.call_args[1] if mock_tui.call_args else {}
    call_args = mock_tui.call_args[0] if mock_tui.call_args else ()
    # initial_task must be 'my task' either as positional or keyword arg
    assert 'my task' in str(mock_tui.call_args), \
        "initial_task='my task' must be passed to run_tui (UXD-001)"
```

---

### DS-12 · UXD-005 — Empty-path approval must not create global grant

**Status:** OPEN. Zero tests found for this path.

```python
@pytest.mark.regression
def test_approval_empty_path_does_not_create_global_grant(tmp_path):
    """Approving a tool call with an empty path must NOT create an approval rule
    that matches all paths. This is a security boundary. DS-12 / UXD-005.
    """
    from teaagent.approval_manager import ApprovalManager
    mgr = ApprovalManager(root=str(tmp_path))
    # Simulate user approving with empty/None path (the dangerous case)
    with pytest.raises((ValueError, TypeError)):
        mgr.approve_call(tool='write_file', path='', scope='path')
    # Alternative: if it doesn't raise, verify the rule is NOT a wildcard
    rules = mgr.list_rules()
    for rule in rules:
        if rule.tool == 'write_file':
            assert rule.path_glob not in ('', '*', '**', None), \
                f"Empty path approval created a global grant: {rule} (DS-12)"
```

---

### DS-13 · UXD-007 — cost_cap=0 must not mean unlimited

**Status:** OPEN. `test_chat_agent_config_cost_cap_zero_passes_through` exists but doesn't
test runtime behaviour — it only verifies the config value is preserved in transit.

```python
@pytest.mark.regression
def test_runner_rejects_run_when_cost_cap_is_zero(tmp_path):
    """runner._core must treat cost_cap=0 as 'zero budget allowed', not 'unlimited'.
    A user who explicitly passes --max-estimated-cost-cents 0 expects no spend. DS-13.
    """
    from teaagent.runner._core import run_with_budget
    blocked = []
    def fake_run(*a, **kw):
        return MagicMock(cost_cents=10.0, status='completed')
    with patch('teaagent.runner._core._execute', side_effect=fake_run):
        try:
            result = run_with_budget(fake_run, max_cost_cents=0, task='test')
            # If it ran, that's the bug — DS-13
            pytest.fail("cost_cap=0 must block execution, not allow unlimited spend")
        except (ValueError, BudgetExceededError):
            pass  # Correct: zero cap must reject the run
```

---

## Appendix A — Module Coverage Heat Map

Modules grouped by functional area for sprint planning:

| Area | Representative modules | Avg coverage | Risk |
|------|----------------------|:------------:|------|
| CLI handlers | `_chat.py`, `_agent.py`, `_env.py`, `_gateway.py` | **~35%** | Critical |
| Approval + security | `approval_manager.py`, `approval_ui.py`, `policy.py` | ~72% | High |
| TUI surface | `tui/__init__.py`, `chat_session_controller.py` | ~84% | Medium |
| Undo + sandbox | `run_undo.py`, `sandbox/_git_branch.py` | ~72% | High |
| Audit chain | `audit.py`, `audit_chain.py`, `run_store.py` | ~84% | Medium |
| Runner core | `runner/_core.py`, `runner/_auto_mode_manager.py` | ~79% | Medium |
| Subagents | `_approval_queue.py`, `_team_orchestrator.py`, `_review.py` | ~58% | High |
| LLM / adapters | `chat_agent.py`, `llm/`, `streaming/` | ~82% | Low |

---

## Appendix B — Two Failing Tests

**`test_mcp_trust.py::test_mcp_trust_policy_serialization`** and
**`test_mcp_trust.py::test_mcp_trust_policy_persistence`** fail in the current suite.
Both are in `cli/_handlers/_mcp_trust.py` (17% coverage). Investigate before raising the
coverage gate, as these may indicate a real regression.

---

*Generated 2026-06-02. Coverage data from pytest-cov 7.14.0, Python 3.11.*
*Cross-references: `docs/analysis/defeat-scenarios-and-cascade-effects-2026-06-02.md` (defeat scenarios),*
*`docs/reviews/daily-driver-findings-status-ledger-2026-06-01.md` (defect status).*
