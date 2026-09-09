# Roadmap and Original-Intent Socratic Review — 2026-09-09

> **Claim class:** Dated review record. Evidence and reasoning only — never
> current-truth authority. `docs/roadmap-status.md` owns status.
> **Trigger (introspection freeze, harness-first §3.2):** owner request to review all
> roadmaps and original intents with Socratic critical thinking, 2026-09-09.
> **Method:** parallel-lens review packet, 7 independent lenses, `HEAD 8b61339`.
> **Owner disposition:** all 10 ledger items adopted 2026-09-09.
> **Last reviewed:** 2026-09-09
> **Review trigger:** ADR-0031 disposition (2026-09-12), DR-006 falsifier window
> close (2026-09-22), or ADR-0043 expiry (2026-12-09).

---

## 1. Verdict

The harness-first **identity** survived scrutiny. Its **evidence semantics** and
**gate enforcement** did not.

Panel: 5 × `DISAGREE`, 2 × `AGREE WITH CHANGES`, 0 × `AGREE` on the question
"is the current roadmap direction sound as written".

**Root cause, one sentence:** the roadmap could not distinguish *no evidence* from
*good evidence*, so unexercised code read as clean and an idle harness read as validated.

## 2. The finding that reframed the review

`.teaagent/runs/runs-index.jsonl` holds **415 runs** spanning 2026-06-03 → 2026-08-31,
comprising exactly **6 distinct task strings**, all synthetic:

| count | task |
| --- | --- |
| 259 | `Update docs/cli.md to document clarify command` |
| 53 | `Reply with exactly: Hello from CLI test` |
| 50 | `Reply with exactly: CLI read-only test pass` |
| 50 | `Reply with exactly: model override works` |
| 2 | `Count the number of Python files in this project` |
| 1 | `Use no tools. Return final answer exactly: live-agent-ok` |

**Zero organic owner tasks are recorded.** Four consequences that no authority doc
previously stated:

1. **ADR-0031 criterion 1 is unexercised, not clean.** "0 shadow events across 5,690
   scanned events" was drawn from 415 repetitions of 6 benchmark prompts in which the
   shadow branches were *structurally unreachable* — no destructive tool, no approval
   decision, no subagent launch. `0` therefore carries no information about the
   false-positive rate. The roadmap previously stated the conclusion ("0 organic ≠
   promotion") without this reason.
2. **G1 has no supporting record.** No organic daily task appears in the run store.
3. **"The owner-operator is the current validated persona" was unsupported** by the
   run store; corrected to *target* persona in `roadmap-status.md`.
4. **The closed-loop defense does not apply to this state.** Harness-first §1
   legitimises the closed evidence loop: "a personal harness validated by its owner's
   daily use and its own gates is exactly a closed loop, on purpose." That is
   *conditional on the owner's daily use being the validating input*. With no organic
   runs recorded, the loop is not closed — it is an open circuit.

**Post-fix measurement (R-01/R-07 landed).** `scripts/prepare_h4_evidence.py` now
reports a reachability denominator and a `verdict`. Measured 2026-09-09:

| Scope | Observed | Reachable runs | Verdict |
| --- | --- | --- | --- |
| ADR-0031 window 2026-08-13 → 2026-09-11 | 0 | **0** | `unexercised` |
| All recorded history | 0 | **4 of 415** | `clean` |

The all-history row is the sharper warning: `clean` is *technically* correct there yet
statistically empty, because only 4 recorded runs ever reached an H4 surface. A verdict
is only as meaningful as its denominator, which is why the denominator is now emitted
alongside it instead of being left implicit. Synthetic demo receipts are additionally
stamped `provenance='synthetic-demo'` and excluded from candidates, so "demo synthetic
≠ C1" is now code-enforced rather than prose-only.

**Falsifier for this finding.** Absence of a recorded organic run is not proof of
non-use. There is no second `runs-index.jsonl` (`~/.teaagent/` has none), but
`~/.teaagent/tui_state.json` was modified 2026-08-31, so TUI/chat paths that never
write the run index could carry unrecorded use. Corroborating activity proxy —
`~/.teaagent/run-keys` entries by month: **Jun 34,488 · Jul 1,444 · Aug 4,193 ·
Sep 111** (through 09-09); steep decline, and recent months plausibly include agent
maintenance sessions. If real use runs through unrecorded paths, the finding weakens
to "no organic runs *recorded*" — still a governance defect (an audit harness that
does not capture its owner's own use), but a different one.

## 3. Claims that passed without meaning

| Claim | Reality | Evidence |
| --- | --- | --- |
| ADR-0031 criterion 2 "coverage completeness passes" | **Vacuous.** 0 workspace policies, 0 roles, 0 declarations, `gaps: []`, `ok: true`. 0/0 rendered as 100% | `.teaagent/policies/*.json` = 0, `.teaagent/roles/*.json` = 0, `coverage.json` |
| `promotion_ready=false` cited as status | **A hardcoded literal**, not an evaluated metric; cannot flip when conditions are met | `teaagent/governance/h4_decision_packet.py:69` |
| "demo synthetic ≠ C1" | **Prose only.** The extractor keyed solely on `event_type`; demo receipts could be ingested as organic | `teaagent/governance/h4_evidence.py` (fixed by R-07) |

## 4. Gate enforcement was dark where it mattered

- CI `lint` was **red on `main`**: `audit_config_access.py --max 65` → 68 violations,
  exit 1 (identical at `66411a1`, so pre-existing). The bare invocation exits 0 while
  printing `FAIL`, so a local check looked harmless.
- `governance-gate`, `review-institution`, `docker-smoke` all declare `needs: lint`
  → **never executed**. That dark set included the permission matrix, governance fuzz,
  plan-before-write, `teaagent selftest`, `tool lint`, audit-schema conformance, and
  the G9 action-register check.
- `package` declared **no `needs:`** → wheels built and smoke-installed while the
  governance tier was dark.
- `validate_event_spine_wiring.py` — the ADR-0032 invariant — ran in pre-commit only
  and was **absent from CI**, so any `--no-verify` or web-UI commit skipped it.
  `validate_runner_invariants.py`, `check_dead_code.py`,
  `validate_control_loop_freshness.py`, and `check_root_module_count.py` were wired to
  neither.
- **Hook/CI argv asymmetry (G9):** the pre-commit hook passes `--commit-msg`, so an
  action ID in the commit *message* satisfied it; CI passed only `--base`, inspecting
  the *diff*. Verified on `8b61339`: `--commit-msg` → exit 0, `--base HEAD~1` → exit 1.
  Local green ≠ CI green by construction.

## 5. Goal integrity: misses relabelled, metrics misreported

| Goal | Was | Verified reality |
| --- | --- | --- |
| G3 one event spine | `Complete — Rescoped` | Only M0, M1-partial, M3 landed. One interceptor (plan gate), one consumer (`AuditLogger`); `AgentRunner` still calls `audit.record()`; `HookRegistry`/`ContextBus` independent (`ContextBus` live in `swarm.py`). The §2 named failure mode — "a fourth parallel system instead of replacing three" — occurred |
| G4 hooks not forks | `Complete — tool dispatch scope` | The ratified example (custom budget rule without touching `AgentRunner`) is unsatisfied; budget is inline in `runner/_core.py`; 6 of 8 lifecycle hooks unwired |
| G5 docs carry weight | `Complete`, "~500-file corpus with 259 archive" | **639** files (8/368/**262**) — a misreport of ~139 files, and growth from the 582 baseline the intent called too expensive |
| G6 tests prove behavior | `Complete`, "586 test files typed" | 603 files; **17** explicit markers, 136 by path heuristic, **454 (75%) fall back to the default `contract`**. Header simultaneously led with `6681 passed`, the exact vanity count §4.2 forbids |

**Thin-harness reality:** `teaagent/` is 502 files / **124,984 LOC**;
`check_god_modules` passes at threshold 800 only via **18 exemptions**, which include
`runner/_core.py` (1,054 lines) — the module the ownership map calls the gravity well.

## 6. Scheduling logic

- **ADR-0031 has one commit** (`d736a1b`, 2026-06-12) and was never amended;
  `2026-09-12` never moved. This is the **first** expiry, not a serial extension —
  genuine dated discipline, and the strongest point in the roadmap's favour.
- **Promotion on 2026-09-12 is arithmetically unreachable** (30-day organic window,
  0 organic events, 3 days). Only `extend` or `revert` are reachable. `extend` is a
  decision only if a dogfood session is *booked*; otherwise it converts temporary
  shadow wiring into permanent dead code — the failure ADR-0031 exists to prevent.
- **DR-006 falsifier 1 was mechanically undecidable**: gates live in
  `backlog-priority.md` prose, unlinked to commits. Of 8 post-DR-006 `feat` commits
  touching `teaagent/`, **7 cited no gate**; only `87d1c61` cited `governance-gap`.
  Fixed by R-08.
- **Friction log:** all 12 entries dated 2026-06-22 (5 owner-evidence closed, 9
  hypotheses open); zero new entries in 79 days.

## 7. Adoption ledger (owner adopted all 10, 2026-09-09)

| ID | Change | Surface | Status |
| --- | --- | --- | --- |
| R-01 | Criterion 1 restated as `unexercised` with a reachability denominator | `roadmap-status.md`, H4 evidence tooling | adopted |
| R-02 | G5 corpus figures corrected (639 / 8-368-262), growth disclosed | `roadmap-status.md:67` | adopted |
| R-03 | G6 typing fallback disclosed; vanity count demoted to historical note | `roadmap-status.md:14,68` | adopted |
| R-04 | G3/G4 relabelled `Partial`; fourth-parallel-system risk named as accepted | `roadmap-status.md:65,66` | adopted |
| R-05 | "validated persona" → "target persona" | `roadmap-status.md:14` | adopted |
| R-06 | CI enforcement repaired (ratchet unblocked, orphan gates wired, argv parity, packaging gated) | `ci.yml`, `.pre-commit-config.yaml` | adopted |
| R-07 | Provenance tagging so synthetic receipts cannot count as organic | `h4_evidence.py`, `prepare_h4_evidence.py` | adopted |
| R-08 | DR-006 falsifier 1 made mechanically checkable via a `Gate:` trailer | `check_dr006_gate_trailer.py`, DR-006 doc | adopted |
| R-09 | Non-goal surfaces quarantined as `legacy-competitive` with a dated expiry | [ADR-0043](../adr/0043-legacy-competitive-surface-quarantine.md) | adopted |
| R-10 | Thin-harness line carries the honest numbers | `AGENTS.md` | adopted |

**Debt accepted in R-06:** the config-access ratchet was *raised* 65 → 68 to match
reality and unblock the dark governance tier. Raising a ratchet is a loosening; it is
recorded here deliberately. The ceiling must only ever decrease, and the 3-violation
debt is owed back.

## 8. Method limits

The 7 lenses are **one epistemic channel** — same model family, same context. Panel
consensus is advisory evidence and never proof of operational behavior. Every
load-bearing number in this record was re-derived by the coordinator with
deterministic commands; lens-only claims are labelled as such in the working record at
`.teaagent/reviews/roadmap-intent-socratic-2026-09-09/synthesis-record.md`.

Coordinator corrections to the panel: archive tier is **262** (two lenses said
263/259); `teaagent/workflow_engine.py` is an **ADR-0030 compat shim**, not a duplicate
engine; the non-goal modules **predate** the decisions that descoped them, so the issue
is retention, not violation. The panel's stronger recommendation — delete the non-goal
surfaces now — was **not** adopted: three are CLI-reachable, and deleting them on a
review's authority would itself be an ungoverned effect.

## 9. References

- [Harness-First Direction](../strategy/harness-first-direction-2026-06-13.md) (G1-G6, non-goals, failure modes)
- [DR-006 Owner Decision](../strategy/dr-006-owner-decision-2026-06-22.md) (scheduling gates, falsifiers)
- [ADR 0031](../adr/0031-shadow-mode-exit-criteria.md) (shadow exit criteria, 2026-09-12 expiry)
- [ADR 0043](../adr/0043-legacy-competitive-surface-quarantine.md) (non-goal quarantine, this review)
- [Roadmap Status](../roadmap-status.md) (canonical current truth)
