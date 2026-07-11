# Control-Plane Operator Cockpit Acceptance Spec (M4 carve-out)

> **Claim class:** Forward-looking specification (planned/held work — NOT current truth).
>
> **Status:** Allowed under DR-006 carve-out (owner-override: co-maintainer dogfood).
>
> **Date:** 2026-07-11
>
> **Trigger:** Owner request 2026-07-11 — forward-spec held/external roadmap items
> so future execution has pinned contracts and executable holds.
>
> **Scheduling gate (DR-006):** `owner-override` — M4 "background lifecycle +
> operator cockpit may proceed under owner-override co-maintainer dogfood"
> (`docs/strategy/dr-006-owner-decision-2026-06-22.md` T1 carve-out;
> `docs/backlog-priority.md` M4 row). Cloud/SaaS/multi-tenant GTM and gateway
> task intake remain **Held** and are out of scope here.
>
> **Owns:** The acceptance definition for the M4 exit criterion
> "control-plane operator cockpit acceptance" and the snapshot schema
> stability contract.
>
> **Does not own:** Current-truth status (`docs/roadmap-status.md`), the hold
> on the rest of M4, cockpit implementation history (SCL-P2-001/CPP-P2-001,
> both Complete).
>
> **Review trigger:** M4 gate evaluation, or any change to
> `COCKPIT_SNAPSHOT_SCHEMA_VERSION`.

## 1. Current verified state (2026-07-11, HEAD)

The cockpit exists on three surfaces sharing one payload:

- **Shared snapshot:** `build_cockpit_snapshot`
  (`teaagent/integration/cockpit_parity.py:16-39`) returns
  `{schema_version, control, pending_approvals, stale_workspace}` with
  `COCKPIT_SNAPSHOT_SCHEMA_VERSION = '1'` (`:13`). `control` is
  `asdict(ControlCockpitState)` from `build_control_cockpit`
  (`teaagent/cockpit.py`), with sections
  `spec, goal, model_route, memory, review, skill, approval, cost,
  last_updated` (verified by `tests/test_control_cockpit.py:16-76`).
- **CLI:** `teaagent cockpit [--root] [--permission-mode] [--human]`
  (`teaagent/cli/_ergonomics_parsers.py:52-69` →
  `teaagent/cli/_handlers/_cockpit.py:12-16`).
- **TUI:** tabbed cockpit screens
  (`teaagent/tui/cockpit_screens.py` — `CockpitTab{WORKFLOWS, APPROVALS,
  COSTS, MEMORY, BACKGROUND}`), data sources with per-source degraded-mode
  behavior (`teaagent/tui/cockpit_data_sources.py` — each source logs and
  returns empty rather than failing the cockpit, e.g. approval-source
  fallbacks at `:454-534`; `CockpitDataManager` at `:695`).
- Existing acceptance/behavior coverage: snapshot core sections + CLI JSON
  contract (`tests/acceptance/test_cockpit_snapshot_flow.py`), CLI/TUI daily
  parity (`tests/acceptance/test_cli_tui_surface_parity_flow.py`,
  `test_daily_cockpit_parity_flow.py`), empty-workspace no-crash
  (`tests/test_control_cockpit.py:60-76`), data sources/screens/renderer
  (`tests/test_cockpit_data_sources.py`, `test_cockpit_screens.py`,
  `test_cockpit_integration.py`), degraded-source classification
  (`tests/test_a_p0_2_observability.py:122-211`).

## 2. The hold and its gate

M4 as a milestone is **Pending (held except DR-006 carve-out)**. This spec
covers only the carved-out cockpit acceptance. Gateway task intake and any
multi-tenant/cloud cockpit surface stay held; nothing here may be read as
scheduling them.

## 3. Future contract — the acceptance definition

### 3.1 Operator questions the cockpit must answer alone

The M4 cockpit acceptance passes when the owner-operator can answer each
question from cockpit output (CLI `--json` payload or TUI tabs) without
reading logs or code:

| # | Operator question | Snapshot/TUI surface |
| --- | --- | --- |
| Q1 | What is running / suspended / blocked right now? | `control.goal`, TUI WORKFLOWS + BACKGROUND tabs (`BackgroundRow`) |
| Q2 | What awaits my approval, and in what scope? | `pending_approvals`, `control.approval.pending_count`, APPROVALS tab |
| Q3 | What have I spent, against what limit, in what state? | `control.cost{spent_cents,…}` + cost_state input, COSTS tab |
| Q4 | Is agent-written memory quarantined and how much? | MEMORY tab quarantine rows (`memory-quarantine.jsonl` count) |
| Q5 | Is my workspace stale relative to disk/git? | `stale_workspace` section |
| Q6 | Which skills/extensions are active? | `control.skill.loaded_count` |
| Q7 | Where did the route/model decision come from? | `control.model_route` |

### 3.2 Schema stability contract

- **Additive-only within a schema version.** Keys never disappear or change
  type while `schema_version == '1'`; removals/renames require a version
  bump plus a dated note in this spec.
- The four top-level sections are frozen for v1:
  `{schema_version, control, pending_approvals, stale_workspace}`. Adding a
  fifth section is a version-review event (the executable pin fails to force
  that review).
- The `control` section must at minimum carry the nine keys listed in §1 —
  the operator-question mapping (§3.1) depends on them.
- The whole payload stays `json.dumps`-serializable with no custom encoder
  (automation consumers: dashboards, `--json` scripting).

### 3.3 Degraded-source contract

Every data source failure degrades to an empty section plus an ERROR log
with recovery hint — never a cockpit crash (already implemented for
approval/memory/quarantine sources; the acceptance requires this property
to hold for **all** sources). Trust rule: a degraded section must be
distinguishable from a genuinely-empty one in logs (the recovery-hint text
names the failed source).

### 3.4 Refresh semantics

- CLI snapshot is point-in-time; `last_updated` timestamps the build.
- TUI refresh piggybacks on session events (`_refresh_control_cockpit`,
  `teaagent/tui/core.py:173-187`); a failed refresh keeps the previous
  state and logs at debug (`:183-185`) — acceptable for v1, revisit only on
  a friction entry about stale cockpit data.

## 4. Executable specification

Tests live in `tests/test_cockpit_acceptance_spec.py`.

| Contract clause | Test | Kind |
| --- | --- | --- |
| Top-level section set + schema version frozen for v1 | `test_snapshot_toplevel_schema_is_frozen_for_v1` | guards contract today — failure = schema change; bump version + update this spec |
| Control section carries the operator-answer fields; inputs are reflected | `test_control_section_carries_operator_answer_fields` | guards contract today |
| Snapshot is plain-JSON serializable and key-stable across builds | `test_snapshot_is_json_serializable_and_key_stable` | guards contract today |

Existing coverage (not duplicated): core-section presence + CLI JSON
emission (acceptance flow tests), empty-workspace defaults, degraded-source
logging, tab/renderer behavior — see §1 list.

## 5. Acceptance checklist for the M4 gate

1. §3.1 table walked through in a real co-maintainer dogfood session
   (owner at the keyboard, one background run + one pending approval + one
   quarantined memory staged); each question answered from cockpit output
   only. Record the session as a dated work-log note.
2. All §4 pins plus the §1 existing suites green.
3. `--human` output passes the plain-language rule (no governance nouns on
   the first line — `soften_operator_copy` behavior, already tested in
   `tests/test_friction_ux_fixes.py:33-38`).
4. Update `docs/roadmap-status.md` M4 row for the cockpit sub-criterion
   (leaving gateway/cloud held), citing the work-log note.

## 6. Risks and open questions

- **Schema drift between CLI snapshot and TUI rows** is the standing risk:
  the TUI reads data sources directly, not the snapshot. v1 accepts this
  (single-process, same stores) with parity pinned only at the daily-view
  level (existing parity flows). A future dashboard must consume the
  snapshot, not the sources — that is what the schema-version discipline
  protects.
- **Stale trust:** `last_updated` is per-build; TUI degraded refresh keeps
  old data silently (debug log only). Acceptable for owner-operator v1;
  becomes a defect the moment a second operator exists (held scenario).
- Open: should `pending_approvals` carry scope details (path globs) in v1
  or wait for a friction entry? Default: wait — Q2 is answerable from
  count + ids today.
