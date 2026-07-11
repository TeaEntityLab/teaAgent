# WDH-002 Real Non-Maintainer Pilot Protocol

> **Claim class:** Forward-looking specification (planned/held work — NOT current truth).
>
> **Status:** External-dependency (not agent-completable).
>
> **Date:** 2026-07-11
>
> **Trigger:** Owner request 2026-07-11 — forward-spec held/external roadmap items
> so future execution has pinned contracts and executable holds.
>
> **Scheduling gate (DR-006):** `external` — WDH-002 requires 3–5 recorded
> sessions with real non-maintainer humans; recruitment remains open and agents
> must not manufacture or relabel simulated evidence
> (`docs/work-log/roadmap-verification-2026-07-01.md:43-45,62-72`).
>
> **Owns:** The ready-to-run protocol, privacy boundary, future real-session
> record contract, evidence-promotion rule, and acceptance checks for WDH-002.
>
> **Does not own:** Current-truth status (`docs/roadmap-status.md`), participant
> recruitment, consent, owner testimony, or the strategic decision to reopen
> external adoption as a current goal.
>
> **Review trigger:** A qualifying participant is available, consent/privacy
> requirements change, or the owner closes/retires WDH-002.

## 1. Current verified state (2026-07-11, HEAD)

### 1.1 What exists

`teaagent/governance/stranger_session.py` provides a **simulation harness**, not
human-research capture:

- `StrangerSessionRecord` (`:19-42`) serializes exactly eight fields:
  `participant_id`, `participant_type`, `concepts_before_first_success`,
  `happy_path_concept_count`, `advanced_disclosed`,
  `completed_happy_path`, `notes`, `captured_at`.
- `concepts_in_copy` (`:45-52`) scans case-insensitively for core concepts
  `ask / approve / undo` (`conversation_ux.py:7`) plus six advanced concepts
  (`:9-16`). It is a substring matcher, not a token parser: `undoable` counts as
  `undo`. That makes it suitable for copy linting, not authoritative human
  measurement.
- `run_simulated_happy_path_session` (`stranger_session.py:55-72`) sets
  `participant_type='simulated_pilot'` and notes that the output is **not** a
  non-maintainer session.
- `run_pilot_battery` (`:75-84`) produces three simulated records.
- `write_session_report` (`:87-99`) hardcodes
  `session_type='simulated_pilot'`; it cannot honestly write a real-human
  report.
- `scripts/capture_stranger_session.py:2,27-29` invokes only that simulated
  battery despite its historical "capture" name.

### 1.2 What the historical work established

The June protocol (`docs/analysis/external-user-session-protocol-2026-06-10.md`)
already fixed the broad shape: 30 minutes, README install, ask → approve → undo,
concept count, screen/terminal/questionnaire, target 3–5 participants. The
execution index records **S6 partial**: harness + three simulated sessions;
non-maintainer recruitment open
(`docs/plans/work-direction-execution-index-2026-06-10.md:79-81`).

Harness-first direction later superseded the simulated-pilot evidence line
(`docs/strategy/harness-first-direction-2026-06-13.md:3-12`) and descoped
external-adoption claims. Therefore:

- the simulated battery is useful only as deterministic tooling/copy coverage;
- it contributes **zero** participants to WDH-002;
- completing WDH-002 supplies a dated external observation, not automatic
  proof that TeaAgent is a daily driver for ordinary developers.

## 2. The hold and its gate

The dependency is a real person who is not a TeaAgent maintainer. An agent
cannot satisfy participant eligibility, informed consent, first-use novelty,
or first-person friction testimony. No additional simulated sessions are
permitted as substitutes. Engineering work is complete once this protocol and
its record validators exist; evidence collection remains human/external.

## 3. Future contract

### 3.1 Participant eligibility

A qualifying participant MUST:

1. have never used TeaAgent or read its internal design/roadmap docs;
2. not have committed to, reviewed, or maintained this repository;
3. be comfortable entering ordinary terminal commands without maintainer
   coaching;
4. explicitly consent to the bounded data collection in §3.2.

Prior agent sessions, maintainer role-play, model simulations, and people who
already know the ask/approve/undo vocabulary do not count toward N.

### 3.2 Consent and privacy

Before recording, the facilitator reads a one-paragraph notice: purpose,
30-minute limit, data captured, voluntary stop, retention, and publication of
redacted aggregates only. Consent is a boolean on the private record; lack or
withdrawal of consent ends capture and excludes the session from N.

Privacy contract:

- use a random pseudonym such as `p-7f2c`; never store name, email, employer,
  account handles, or demographic inference;
- use a disposable local fixture workspace containing no participant data;
- raw terminal/screen recordings remain outside git in an owner-controlled
  directory such as `~/.teaagent/research/wdh-002/<participant_id>/`, mode 0700;
- scrub home paths, tokens, provider keys, repository remotes, and typed free
  text before analysis;
- retain raw material for at most 30 days after owner adjudication, then delete
  it; retain only the redacted record and aggregate findings;
- commit no raw recording or transcript. A dated aggregate findings document
  may be committed after owner review.

### 3.3 Session script (30 minutes, no improvisation)

**Pre-flight (5 minutes).** Verify disposable workspace, local/fake provider,
recording destination, consent, and participant eligibility. Start a timer only
after consent.

**Task (20 minutes).** Give only this prompt:

> Use TeaAgent to make one harmless text-file change. Decide whether to approve
> it, verify the result, then undo it.

The facilitator may answer procedural safety questions ("you may stop") but
MUST NOT name commands, explain governance vocabulary, point to docs, or fix an
error. The participant may consult whatever the README/CLI exposes naturally.
Think-aloud is invited, never coached.

**Debrief (5 minutes).** Ask, verbatim:

1. What did you expect to happen?
2. Where did you feel uncertain or blocked?
3. Which words required explanation?
4. Would you know how to recover tomorrow without this session?

### 3.4 Future real-session record schema (not implemented)

The current `StrangerSessionRecord` cannot represent consent, timing, or
lookups and is explicitly simulated. Add a separate `ExternalPilotRecord`
rather than weakening that truth label:

| Field | Type / rule |
| --- | --- |
| `schema_version` | literal `1` |
| `participant_id` | random pseudonym; no PII |
| `participant_type` | literal `non_maintainer_human` |
| `consent_obtained` | true for retained records |
| `captured_at` | UTC ISO-8601 |
| `task_completed` | bool: change + verify + undo all completed |
| `time_to_first_success_seconds` | integer or null if none |
| `doc_lookup_count` | non-negative integer |
| `concepts_before_first_success` | ordered canonical strings encountered |
| `friction_observations` | redacted factual observations, not interpretations |
| `participant_quotes` | optional redacted quotations approved for retention |
| `facilitator_interventions` | every intervention; empty is ideal |
| `evidence_status` | `pending_owner_review | accepted | excluded` |
| `exclusion_reason` | required when excluded |

A future real capture command MUST write only this schema and MUST NOT call
`write_session_report`, whose hardcoded simulated label is correct for its own
purpose.

### 3.5 Metrics, target, and stop rules

Primary measures:

- completion rate for the full ask → approve → verify → undo path;
- time to first successful change;
- concepts encountered before first success (target ≤3 core concepts);
- documentation lookups;
- facilitator interventions;
- repeated friction categories across participants.

Target N = 3–5 **accepted** records. Stop early only for: safety/privacy issue,
consent withdrawal, or the same blocking failure in two sessions (pause study,
fix only after owner converts it to a friction entry, then restart with fresh
participants). Do not stop early because results look positive.

### 3.6 Evidence promotion and claim boundary

1. New record starts `pending_owner_review`.
2. Owner verifies eligibility, consent, redaction, and intervention log.
3. Excluded records retain only pseudonym + exclusion reason; they do not count.
4. Accepted records roll into a dated aggregate findings document with N,
   method, failures, and residual uncertainty.
5. Owner links accepted friction observations into
   `docs/work-log/operator-friction-log.md` when they affect owner-operated
   usability. Agents may prepare the link; owner decides evidence status.
6. WDH-002 closes only when the execution index points to ≥3 accepted records.
   It does **not** reopen external-adoption/product claims; that requires a
   separate owner-ratified direction decision.

## 4. Executable specification

Companion tests: `tests/test_external_pilot_protocol_spec.py`.

| Contract clause | Test | Kind |
| --- | --- | --- |
| Simulated record's eight-field schema remains explicit | `test_simulated_record_schema_is_pinned` | guards current tooling truth |
| Simulated battery cannot be mistaken for real evidence | `test_simulated_session_is_labeled_non_evidence` | guards claim boundary today |
| Simulation report round-trips with hardcoded simulated type | `test_simulated_report_roundtrip_preserves_truth_label` | guards claim boundary today |
| Core concept detection + known substring limitation | `test_concept_detection_contract_and_substring_limit` | guards measurement assumptions |
| `ExternalPilotRecord` future schema | `test_real_external_record_schema_activates` | activates on implementation (skipif until §3.4 exists) |

## 5. Session-day runbook

1. Confirm §3.1 eligibility without collecting identifying detail.
2. Prepare disposable fixture; remove provider secrets; set private raw-data
   directory permissions.
3. Read consent notice; record consent; start timer.
4. Run §3.3 exactly; record interventions and doc lookups contemporaneously.
5. Stop recording; scrub raw material before any analysis.
6. Validate future `ExternalPilotRecord` against §3.4; set
   `pending_owner_review`.
7. Owner accepts/excludes; update aggregate findings and evidence links.
8. Delete raw data within 30 days of adjudication.

## 6. Risks and open questions

- **Observer effect:** think-aloud and screen capture can slow the participant.
  Report the method; do not "correct" timings.
- **Maintainer contamination:** one command hint invalidates first-use evidence;
  record it and normally exclude the session.
- **Schema drift:** current simulated schema is pinned; future human schema has
  its own version. Never overload `participant_type` to blur them.
- **Substring concept counts:** `concepts_in_copy` can count `undo` inside
  `undoable`. Human records should use observed UI labels, not automatically
  run arbitrary transcript prose through this helper.
- Open: whether participant quotes may be committed at all. Conservative
  default: aggregate paraphrases only unless explicit quote consent is added.
