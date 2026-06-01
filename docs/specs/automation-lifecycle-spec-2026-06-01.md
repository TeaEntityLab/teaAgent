# Automation Lifecycle Specification
# 2026-06-01

**Fills:** Gap **F-ECO-012** — *"add automation lifecycle acceptance beyond creation and
tick: review, renew, pause, resume, promote, transfer, expire, and explain skip."*

**Grounding (current state, verified).**
- **`teaagent/automations.py`** (538 lines): `AutomationSpec{schedule, last_status,
  provenance_digest, next_run_at, …}`, `AutomationStore` with a **quarantine dir**
  (`.teaagent/automations-quarantine`), `draft()`, `compute_next_run_at(schedule)`.
- Supporting modules exist: `automation_chain.py` (190), `automation_collector.py`
  (285), `automation_delivery.py` (105), `automation_limits.py` (72),
  `automation_observability.py` (157), `automation_templates.py` (68),
  `automation_ticket.py` (447), `provenance_gate.py`.
- **What exists:** create/draft, provenance digest (gate), quarantine, scheduling
  (`next_run_at`), `last_status`, budgets/limits, delivery, observability.
- **What's missing:** explicit **lifecycle state transitions** beyond
  create + tick — the verbs F-ECO-012 names.

---

## Lifecycle state machine (the missing layer)

```
draft ──promote──▶ active ──pause──▶ paused ──resume──▶ active
  │                  │                                    │
  │                  ├──(provenance fail)──▶ quarantined ─┘ (re-review)
  │                  ├──(schedule end / TTL)─▶ expired
  │                  └──transfer(owner)──────▶ active (new owner)
  └──reject──▶ discarded
```

Each transition is **audited** and **explainable** (why did this run skip / pause /
quarantine?).

| State | Meaning | Entry | Backed by today |
|-------|---------|-------|-----------------|
| draft | created, not scheduled | `draft()` | ✓ |
| active | scheduled, eligible to run | promote | partial (`next_run_at`) |
| paused | scheduled but suspended | pause | ✗ **add** |
| quarantined | provenance/limit violation | gate fail | ✓ (`quarantine_dir`) |
| expired | past TTL / schedule end | expire | ✗ **add** |
| discarded | rejected draft | reject | ✗ **add** |

---

## Lifecycle verbs to add

| Verb | Effect | Audit event | Acceptance |
|------|--------|-------------|-----------|
| `promote` | draft → active; sets `next_run_at` | `automation_promoted` | scheduled after promote |
| `pause` | active → paused; clears next run | `automation_paused` | no tick fires while paused |
| `resume` | paused → active; recomputes `next_run_at` | `automation_resumed` | ticks resume |
| `renew` | extend TTL / re-affirm provenance | `automation_renewed` | expiry pushed out |
| `expire` | active → expired at TTL/schedule end | `automation_expired` | no tick after expiry |
| `transfer` | change owner identity | `automation_transferred` | new owner in audit lineage |
| `review` | show spec + last N runs + pending state | (read) | lists status, next run, owner |
| `explain-skip` | why a due run did not execute | (read) | returns reason (paused/limit/budget/provenance) |

---

## Behavioral requirements

1. **Every transition is owner-attributed and audited.** Automations act unattended;
   the audit lineage is the only accountability (UX-F7). `transfer` must preserve
   lineage, not erase it.
2. **Missed-run remediation is explicit.** If a scheduled run is skipped (paused, over
   budget, provenance fail, host down), `explain-skip` returns the reason and the next
   eligible time — never a silent no-op.
3. **Provenance re-check on renew.** `renew` re-affirms `provenance_digest`; a changed
   digest forces re-review (→ quarantined), not auto-continue.
4. **Budgets/limits are lifecycle-aware.** An automation that exhausts its budget
   (`automation_limits`) auto-pauses with an `explain-skip` reason, not crashes.
5. **Stale automation cleanup.** `expire` + a `review` listing of stale automations
   gives operators a cleanup path (F-ECO-012 "stale automation cleanup").

---

## Acceptance

- `test_automation_promote_schedules`, `test_automation_pause_no_tick`,
  `test_automation_resume_ticks`, `test_automation_expire_stops`.
- `test_automation_transfer_preserves_lineage`.
- `test_automation_explain_skip_reasons`: paused / over-budget / provenance-fail / down
  each return a distinct reason.
- `test_automation_renew_reaffirms_provenance`: changed digest ⇒ quarantine, not run.
- `test_automation_review_lists_state`: review shows status, next_run, owner, last_status.

## Open decisions

- **DQ-AUTO-1:** Is owner `transfer` needed for v1, or defer (single-owner assumption)?
  Recommendation: defer transfer; ship pause/resume/expire/explain-skip first.
- **DQ-AUTO-2:** Should expiry be wall-clock TTL, run-count, or schedule-end? Recommend
  support TTL + schedule-end; run-count later.

## Non-goals

- Not a general cron/workflow engine (NG-3 — that boundary stays outside core).
- Not auto-promotion of drafts; promotion is an explicit, audited human/owner action.

## Cross-references

- Permission/governance: `permission-mode-risk-decision-table-2026-06-01.md`
  (automation row — `prompt` mode is unusable unattended; DQ-4).
- Operator P-OPS journey: `daily-driver-persona-journey-maps-2026-06-01.md`.
- Evidence per run: `run-evidence-bundle-spec-2026-06-01.md`.
</content>
