# Total Review - The Real Situation

**Date:** 2026-06-04 · **Measured baseline:** `4695d46` · **Interpreter under test:** Python 3.12.8 (CI contract)
**Method:** every claim below is backed by a re-run command, not by an existing doc. Where a doc and the code
disagree, the **code at HEAD wins** and the doc is flagged.

---

## 0. Why this doc exists

The prior review in this repo's memory recorded the suite as **RED — 148 failures at `2715938`
(2026-06-03)**. That finding was correct *when written* and is now **superseded**. Between then and now the
team landed a run of commits whose messages are themselves the story:

```
4695d46 Keep security auditing focused on the base install
f26bf4f Keep the test suite honest under tight runtime limits
dc1ad17 Make the CI-grade test surface honest enough to trust
ebafd43 Make SSH signature verification use the real OpenSSH contract
6b50e0a Restore real protection coverage in the test suite
54f9947 Make TUI status and resume guards reflect the real test surface
b5225b0 Keep the suspend story honest while blocking run-id misuse
df31010 Verify and harden 7 claimed fixes: add tests, fix gaps
```

This is the central fact of the last 24 hours: **the suite was repaired and the docs were partially
re-anchored.** Do not trust any "as of 2026-06-03" claim without re-running.

---

## 1. Test health — VERIFIED GREEN

```
$ /tmp/tea312/bin/python -m pytest -q          # Python 3.12.8
3355 passed, 22 skipped, 150 warnings, 22 subtests passed in 135.39s
$ grep -cE "FAILED|ERROR " run.txt
0
```

- **3,377** tests collected; **3,355 passed; 0 failed; 22 skipped.** Exit code 0.
- Reproduced on the **supported** interpreter, so this is not a version artifact.
- The CPA's "441 acceptance passing / 3,359 tests" is **accurate**, and its "ON TRACK" framing is — *as of
  this hour* — **true**.

**The honest qualifier:** this green is **< 1 day old.** A suite that went 148→0 failures in a day is a suite
whose stability has not yet survived a week of normal churn at 23 commits/day. Treat green as *achieved*,
not *proven*.

---

## 2. Previously-OPEN findings — now mostly closed

| Finding | 2026-06-03 status | Baseline `4695d46` | Evidence |
|---------|-------------------|--------------|----------|
| CG-13 — `except (AttributeError, TypeError): pass` in controller | OPEN | **FIXED** (string absent) | `grep` returns nothing in `chat_session_controller.py` |
| CG-14 — stale `audit_trail` field in chat_repl | OPEN | **FIXED** (field absent) | `grep` returns nothing in `cli/_handlers/chat_repl.py` |
| CG-11 / CG-12 — TUI controller/cost wiring | OPEN(ledger) | already fixed earlier | TUI tests green |
| AG-01 — `task_for_run` raises with no `run_started` | OPEN | **raise still present** at `run_store.py:209`, but suite green | resume tests pass ⇒ `run_started` now written at suspend (commit `b5225b0`) |
| Destructive-tool approval gate (SAFETY) | FAILING (`failed:permission`) | **passing** | `df31010` "Verify and harden 7 claimed fixes" |

The findings ledger (`daily-driver-findings-status-ledger-2026-06-01.md`, last anchored 2026-06-01) is now
**stale in the optimistic direction is corrected, but it is stale in the pessimistic direction** — it still
lists items as OPEN that HEAD has closed. Re-anchor it or mark it superseded.

---

## 3. Structural facts (all re-measured)

| Fact | Value | Note |
|------|-------|------|
| AgentRunner | `teaagent/runner/_core.py`, **757 lines** | matches CPA exactly |
| LLM providers | **14** `ProviderConfig` entries in `llm/_config.py` | matches "14+" |
| Coverage gate | `--cov-fail-under=75` (`ci.yml:112`) | matches "75% gate" |
| Coverage `omit` | **16 entries** | `tui/*`, `tournament/*`, `validation/*`, `workflow_engine`, `vote_relay`, `tls_server`, `webhook_sink`, `wasm_runtime`, `wasm_skill`, `tsb_format`, `workspace_tools/{builder,_git,_config}`, `browser_tools`, `cli/_handlers/{_cost,_control_plane}` |
| ADRs | **31** files, **6 Proposed** | proposed = 0010, 0012, 0014, 0015, 0017, 0018 |
| Ticket plans | **21** | `docs/plans/ticket-plans/*.md` |
| Module doc dirs | **28** | `docs/modules/*/` |
| CLI handler modules | **35** (54 files under `teaagent/cli/`) | CPA's "170+ handlers" counts subcommands, not files |

---

## 4. The duplicate-class claims — measured, then reframed

### 4a. `ApprovalManager` ×2 — name collision, **not** a behavioral fork
- `teaagent/approval_manager.py:604` — the **policy engine** (861-line module: JIT state, multi-sig quorum,
  peer signatures, `assert_allowed`).
- `teaagent/runner/_approval_manager.py:13` — a **140-line workflow wrapper** for `AgentRunner` that *imports*
  `ApprovalPolicy` from `policy.py` and orchestrates request/handler/audit callbacks.

These are **different responsibilities that happen to share a class name.** The risk is a *cognitive* hazard
(grep ambiguity, accidental wrong import), not "two implementations whose behavior diverges." **Reframe the
CPA's HIGH → Medium.** Fix = rename one (e.g. `RunnerApprovalCoordinator`), don't "merge."

### 4b. `policy.py ↔ approval_manager.py` circular import — **managed**, not live bug
- `policy.py:17` imports `ApprovalManager` from `approval_manager.py`.
- `approval_manager.py:299-300` **lazy-imports** `ApprovalPolicy` with the explicit comment
  *"Lazy import to avoid circular dependency."*
- Both modules import cleanly in isolation (`python -c "import teaagent.policy"` → OK; same for
  `approval_manager`). **No import-order explosion reproduces.**

**Reframe the CPA's HIGH → Low.** It is a latent maintenance hazard (lazy import is a smell), not a
ticking bomb.

### 4c. `MemoryCatalog` ×2 — the question is answerable: one is **dead code**
- Canonical: `teaagent/memory_legacy.py:42`, re-exported by `teaagent/memory/__init__.py:18`. **Every**
  importer in the codebase uses `from teaagent.memory import MemoryCatalog` → resolves to legacy.
- Orphan: `teaagent/memory/catalog.py:37` defines a second `MemoryCatalog` that **no module or test imports**
  (`grep "memory.catalog import"` → zero hits).

**Reframe the CPA's HIGH ("which is canonical?") → Medium dead-code cleanup.** The answer is: legacy is
canonical; **delete or wire `memory/catalog.py`.** Leaving an unreferenced same-named class is a future
foot-gun (someone will "fix" the wrong one).

---

## 5. `DANGER_FULL_ACCESS` — real bypass, by design

`teaagent/approval_manager.py:197-201`:
```python
if self.permission_mode in {PermissionMode.ALLOW, PermissionMode.DANGER_FULL_ACCESS}:
    return None     # no approval required
```
The CPA calls this "CRITICAL — bypasses all approval gates; add external control or remove." **Measured:** it
does bypass, but this is a **deliberate, named opt-in escape hatch** — the industry-standard equivalent of
`--dangerously-skip-permissions` / "YOLO mode." Removing it would not match peer tools.

**Reframe CRITICAL → Medium, scoped to two falsifiable questions:**
1. Is entering `DANGER_FULL_ACCESS` itself **audited** (hash-chained event at mode-switch)?
2. Is it **hard to enable accidentally** (explicit flag/confirmation, never a default, never silent from
   config)?
If both are yes, the residual risk is acceptable for a power-user tool. (Both warrant a dedicated test;
see [Future Outlook](total-review-future-outlook-2026-06-04.md).)

---

## 6. Live drift items at the measured baseline

| # | Drift | Evidence | Severity |
|---|-------|----------|----------|
| D-1 | `acceptance.md` self-contradicts | headline "441 passed" (correct) vs body line 144-145 "as of 2026-06-03 ... 3255 passed, **26 failed**, 76 skipped" (baseline suite evidence is 3355/0/22) | Medium - guarded doc states a false full-suite number |
| D-2 | Local dev interpreter unsupported | `.venv` = Python **3.14.4**; `pyproject` `requires-python>=3.10` targeting 3.10–3.12 | Medium — devs test on an interpreter CI never runs |
| D-3 | Findings ledger stale | `…ledger-2026-06-01.md` last anchored 2026-06-01; lists closed items as OPEN | Low — but it self-declares "authoritative for status" |
| D-4 | Orphan `memory/catalog.py` | 0 importers (see §4c) | Low |
| D-5 | 6 Proposed ADRs unexecuted | 0010/0012/0014/0015/0017/0018 | Low — decisions deferred = decisions made by default |
| D-6 | 1 production stub returns fake data | `issue_intake.py:195` `# TODO: GitHub API` returns mock `ParsedIssue` instead of raising | Medium — silently misleads callers |

Supersession note, 2026-06-04: D-1 was fixed in the documentation
optimization pass by replacing the stale failure paragraph with dated
full-suite evidence wording in `docs/acceptance.md`.

---

## 7. What is genuinely strong (don't lose this in the critique)

- **Test pyramid is real and now green** — 3,355 passing, `FakeAdapter` deterministic LLM mock, temp-workspace
  isolation. This is the load-bearing asset.
- **Zero mandatory runtime deps on the core path** — verified by the stdlib-only import posture; rare and
  valuable for a security-sensitive agent.
- **Hash-chained audit + 5-tier permission model + multi-sig quorum** — the approval engine is substantial
  (861 lines) and tested.
- **ADR discipline** — 31 ADRs mean architectural decisions are captured, not lost in chat history.
- **The team self-corrects fast** — 148→0 failures in a day, with commit messages that name the honesty
  problem rather than hiding it. That culture is worth more than any single artifact.

---

## Reproduction

```bash
git rev-parse HEAD                              # 4695d46…
uv venv --python 3.12 /tmp/tea312
VIRTUAL_ENV=/tmp/tea312 uv pip install -e ".[dev]"
/tmp/tea312/bin/python -m pytest -q            # -> 3355 passed, 0 failed, 22 skipped
```
