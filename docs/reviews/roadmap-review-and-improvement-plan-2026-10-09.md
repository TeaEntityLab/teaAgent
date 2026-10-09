# Roadmap Review and Improvement Plan — 2026-10-09

> **Claim class:** Dated whole-project review and **proposed** roadmap; not current truth and not a scheduling authority.
> **Status:** Review recorded 2026-10-09. Every implementation row below is `Proposed` until the owner admits it through the DR-006 gate or it qualifies as a `fix:` on an existing contract.
> **Owner:** docs
> **Last reviewed:** 2026-10-09
> **Review trigger:** Owner disposition of §6 asks; `main` returns to green; ADR-0031 or ADR-0043 is decided; a new owner-use evidence entry lands.
> **Repository HEAD observed:** `12eb7a80` (2026-09-30). Clone was shallow (depth 50) at the start of the review and was unshallowed (1,428 commits) before any history-dependent check was trusted.
> **Action register:** G-P2-21.
> **Authority, in order:** [Harness-First Direction](../strategy/harness-first-direction-2026-06-13.md) → [DR-006](../strategy/dr-006-owner-decision-2026-06-22.md) → [Roadmap Status](../roadmap-status.md) → [Backlog Priority](../backlog-priority.md) → ADRs → [Held Roadmap Forward-Spec Index](../specs/held-roadmap-forward-spec-index-2026-07-11.md) → dated reviews such as this file and [Roadmap Rethink 2026-09-16](roadmap-rethink-2026-09-16.md).

---

## 1. Verdict in one paragraph

TeaAgent is **governance-mature, evidence-starved, and currently red on `main`.** The harness itself is in better shape than its own status pages suggest: the smoke tier passes, the structural gates (god modules, circular imports, root-module freeze, docs consistency) pass, MCP serve is now governed and audited (2026-09-24), and the EFX runtime guards exist. But three facts dominate the next quarter and none of them is a feature:

1. **`main` has failed CI on eight consecutive runs since 2026-09-29** (runs 851–858). The failing jobs are `test (ubuntu-latest, 3.12)` and `acceptance-all`. The CI log names **9 failing tests**; this review reproduced **8 of 9 off-runner** in a shallow clone and **2 of 9 with full history**. The repo's own CI debt register ([testing-standards.md](../governance/testing-standards.md) §"CI Runner Environment Notes") says the causes "are not yet reproduced off-runner". That statement is now false and should be corrected (§3.1).
2. **The ADR-0031 decision date (2026-09-29) has passed with no recorded disposition.** The [readiness checklist](../work-log/adr-0031-2026-09-29-readiness-checklist.md) is 0/8 signed; no promote/extend/revert entry exists in the ADR, the roadmap, or any work-log dated after 2026-09-17. ADR-0031 itself names this outcome ("permanent shadow") as the anti-pattern it was written to prevent.
3. **The agent lane is exhausted and the owner lane has not started.** G1 is `unexercised` (0 `origin: owner` runs of 1,538), B1 owner-observed coding testimony is pending since 2026-09-15, the friction log has had no owner entry since 2026-06-22, and the quarterly competitive survey (DR-006 T5, due end of September) has no record. The roadmap cannot generate its own fuel; only the owner can.

Recommendation: spend the next two weeks on **restoring green and recording the overdue decisions**, then run **one owner-observed coding session**, and let its evidence (or its explicit absence) decide the 2026-12-09 quarantine disposition. Do not open any new product horizon in that window.

## 2. Evidence and verification boundary

Everything below was executed in this session unless marked *read*. Numbers are quoted, not rounded to slogans (AGENTS.md architecture rule).

| Check | Result | What it establishes / does not establish |
| --- | --- | --- |
| `scripts/run_test_tier.py --tier smoke` (venv, Python 3.12.3, `PYTHONHASHSEED=0`) | 203 passed, 1 skipped, 19.6 s | Smoke tier is healthy off-runner. Not a full-suite claim. |
| GitHub Actions CI, branch `main`, last 8 runs (851–858, 2026-09-29→09-30) | all `failure`; failing jobs `test (ubuntu-latest, 3.12)` and `acceptance-all`; 13 other jobs green | Red main is real and persistent, and it is **test failures, not runner termination** (the job logs reach the pytest summary: `9 failed, 6752 passed, 25 skipped` and `1 failed, 672 passed`). |
| Re-run of the 9 CI-failing tests locally, **shallow clone** | 8 failed, 1 passed | Shallow history reproduces 8 failures; "runner-specific" is not the cause for those 8. |
| Same 9 tests, **after `git fetch --unshallow`** | 2 failed, 7 passed | 6 failures are caused by missing git history in the `test`/`acceptance-all` jobs (no `fetch-depth: 0`). |
| `test_rollback_refuses_when_head_not_on_sandbox_branch` with `git -c init.defaultBranch=main` | passes | The failure is a test assumption that `git init` creates `main`; GitHub runners default to `master`. |
| `tests/test_evidence_ledger.py::test_real_delivery_ledger_passes` | fails in any fresh clone | It globs `.teaagent/delivery/*/evidence-ledger.yaml`, and `.teaagent/` is in `.gitignore`. It can only pass on the owner's machine. |
| `tests/acceptance/test_run_evidence_summary_flow.py::test_real_run_receipt_completeness_from_plan` | passes locally; fails in CI with missing fragment `'[exit '` | **Reproduced later the same day** by removing `rg` from `PATH`: the fake-adapter verify step runs `rg`, the inspect tool raises `FileNotFoundError`, the runner records `tool_call_failed`, and the receipt renders the command with no outcome. GitHub `ubuntu-latest` ships no ripgrep. The first-run-banner lead recorded earlier was wrong (the banner is gated on `<root>/.teaagent/welcomed`, never on `HOME`). |
| `scripts/check_god_modules.py`, `check_root_module_count.py`, `check_circular_imports.py` | OK with 18 exemptions; root modules 177 ≤ 184; no cycles | Structural gates hold. |
| `bash scripts/verify_docs.sh` (venv on PATH) | passes | Docs gates are green on the untouched tree. |
| Size (this tree) | `teaagent/`: 502 files / 125,500 LOC; `tests/`: 616 test files / 137,511 LOC; `docs/`: 667 Markdown files (807 repo-wide) | Harness grew by 516 LOC since the 2026-09-09 measurement (124,984). Thin-harness remains a target, not a description. |
| Code-health counters | 2,259 `Any` occurrences; 19 `type: ignore`; 30 skip markers; 0 xfail; 3 TODO/FIXME; 10 compat shims in `_compat_modules.py` | Debt is bounded and visible; none of these is a release blocker. |
| GitHub: open issues / open PRs | 0 issues; 8 open PRs, all Dependabot (created 2026-06-26…07-31, last touched 2026-09-14) | Dependency bumps are stalled behind red CI. |
| Release cadence | last tag `v0.1.0-p4-remediation`; 963 commits since; `pyproject` version `0.1.0` | No release has shipped from the last ~960 commits. |
| Owner-use evidence (*read*: roadmap-status 2026-09-17 review) | G1 `unexercised`: 0 organic / 1,216 synthetic / 322 unknown of 1,538 runs; H4 packet 9 observed / 22 reachable / 1 candidate `needs_review` | No positive owner denominator exists. Absence is not zero demand. |

Not executed: the full unit suite with coverage (CI's 16-minute job), live-provider calls, owner testimony, enforcement flips, deletions, or any change to permission modes.

## 3. Findings

### 3.1 F1 — Red `main` is misdiagnosed, and five of the nine failures share one two-line fix

The nine failures in run 858 (`test (ubuntu-latest, 3.12)` job `109721112346`; `acceptance-all` job `109721655607`), classified by this review:

| # | Test | Root cause (verified) | Class | Proposed repair |
| --- | --- | --- | --- | --- |
| 1 | `test_check_dr006_gate_trailer.py::test_real_history_87d1c61_passes` | commit `87d1c61` absent from a shallow checkout | CI config | `fetch-depth: 0` on the `test` and `acceptance-all` checkouts (the 09-29 fixes added it only to `use-case-matrix`, `lint`, `review-institution`) |
| 2–5 | `test_refresh_competitive_docs.py` (4 tests) | `cc7bed6` made the docs-aging check **fail loud** on shallow clones; the refresh script embeds that check | CI config + test design | same `fetch-depth: 0`; additionally make the four tests `pytest.skip` when `git rev-parse --is-shallow-repository` is true so a contributor's shallow clone does not fail |
| 6 | `test_report_docs_aging.py::test_check_docs_aging_dashboard_passes_for_repo` | same shallow-clone guard | same | same |
| 7 | `test_evidence_ledger.py::test_real_delivery_ledger_passes` | reads `.teaagent/delivery/**`, which is gitignored; can only pass on the owner's machine | test depends on local-only state | either commit a minimal fixture ledger under `tests/fixtures/` and point the test at it, or skip when no ledger exists. Do **not** delete the validator tests that use synthetic ledgers. |
| 8 | `test_g2_g3_g22_focused.py::test_rollback_refuses_when_head_not_on_sandbox_branch` | `git init` then `git checkout main`; runners default to `master` | test assumption | `git init -b main` (git ≥ 2.28) or read the created branch name and check it out |
| 9 | `acceptance/test_run_evidence_summary_flow.py::test_real_run_receipt_completeness_from_plan` | the verify step runs `rg`; GitHub `ubuntu-latest` has no ripgrep, so `workspace_run_shell_inspect` raises `FileNotFoundError`, the runner records `tool_call_failed`, the run still completes, and `extract_commands_run` / `format_run_receipt` ignore `tool_call_failed`, so the command renders with no `[exit N]` | test environment **and** a receipt-honesty gap | (a) test uses POSIX `grep` instead of `rg` (assertions unchanged); (b) `governance-gap`: `extract_commands_run` consumes `tool_call_failed` and the receipt renders `[failed: <error>]` / `[outcome unknown]` instead of silence. Never emit a fake `[exit `. |

Why this matters beyond green badges: the 2026-09-30 debt register says the causes are "not yet reproduced off-runner" and earlier phrasing blamed "runner resource termination". The logs contradict both. Under this repository's own documentation operating model, a claim that is contradicted by an artifact the repo can read is a **claim-hygiene defect** (same class as the 2026-09-09 "CI-dark" findings). The register entry should be rewritten to the table above in the same commit that fixes #1–#8.

Falsifier for this finding: if, after `fetch-depth: 0` plus repairs #7 and #8, `acceptance-all` or `test (ubuntu-latest, 3.12)` still fails on something other than #9, the diagnosis was incomplete.

### 3.2 F2 — Three dated decisions are overdue or imminent, and silence is the forbidden outcome

| Decision | Due | State on 2026-10-09 | Rule that is being violated by silence |
| --- | --- | --- | --- |
| ADR-0031 shadow→enforce: promote / extend / revert | 2026-09-29 | No entry; checklist 0/8; packet 4/5 `prepared`, criterion 1 `needs_review`, D1 unadjudicated | ADR-0031 §Expiry: "missing the date means extend/revert review, never silent enforcement" and never silent shadow either |
| DR-006 three-month falsifier review | ~2026-09-22 | F1 mechanically green (`check_dr006_gate_trailer.py`); F2–F4 unexercised; no dated review record | DR-006 §Falsifiers (calendar reminder, not authority expiry — but a record was promised) |
| DR-006 T5 quarterly competitive survey (docs-only hypothesis intake) | end of September | No record of a run or of an explicit skip | T5 Option C |
| ADR-0043 quarantine disposition (8 register rows) | 2026-12-09 | Prepared: `domain/workflow_engine.py` importer sweep shows 0 production callers; ANP row added 2026-09-17 | Not yet overdue; needs a scheduled owner slot |
| ADR status reconciliation: ADR-0007, 0019, 0020, 0021 read "Accepted and Implemented" for surfaces ADR-0043 brands `legacy-competitive` | with ADR-0043 | Flagged 2026-09-17, unresolved | ADR consistency rule in doc taxonomy |

Recommendation for ADR-0031 (this is a **proposal**, the verdict is owner-only): the ADR text and the 2026-08-31 advisor both make **revert** the default when no organic events exist and no owner session is booked. A bounded alternative that keeps the option open is: *extend once more to a named date no later than 2026-11-15, bound to a booked B1 session; if that session does not occur, revert without a further review.* Either outcome must be written into the ADR plus a dated work-log, and the readiness checklist must be closed or superseded as its own header requires.

### 3.3 F3 — Evidence starvation is structural, not an oversight

- Friction log: 5/5 owner entries closed on 2026-06-22; 3 hypotheses carry agent-verified closure evidence since 2026-09-14 and wait only for owner validation; zero new owner entries in 109 days.
- Run store: 0 `origin: owner` runs. 65 `origin: dogfood` runs are fake-provider sessions. The one booked M4 session (2026-09-15) produced B2/B3 agent evidence and an explicitly **partial** PTY run (0 tool calls, 0 file changes).
- Consequence: every DR-006 lane except `governance-gap` is starved, exactly as the 2026-08-31 advisor predicted. G1, G2 field validation, H4 criterion 1, BG-001, and the 12-09 disposition all wait on the same missing input: one real coding task run by the owner through the harness.

This is not fixable by agents and should stop appearing in agent work queues as if it were. The plan below treats the owner session as a **milestone with a date**, not a background hope.

### 3.4 F4 — Process and debt observations (none blocking, all cheap to ratchet)

| Observation | Evidence | Proposed disposition |
| --- | --- | --- |
| Debt register wording contradicts CI logs | §3.1 | Rewrite in the green-main commit |
| `scripts/run_acceptance_tier.py` shells out to a literal `python3` instead of `sys.executable` | script line `cmd = ['python3', '-m', 'pytest', …]` | One-line portability fix; prevents venv/system drift between the tier runner and the interpreter that launched it |
| Test job wall time 16 min 25 s on the canonical cell | run 858 | Acceptable today; set a soft budget (20 min) and watch the trend; do not add coverage-heavy tests to the smoke tier |
| 18 god-module exemptions, largest `tui/core.py` 1,568 and `approval/manager.py` 1,473 lines | `check_god_modules.py` | Keep the "no new exemption" rule absolute; retire at most one exemption per quarter and only when a behavior-preserving split is already required by other work (`cli/_agent_parsers.py` is the designated A-P2-2 target) |
| 2,259 `Any` occurrences | grep | Add a `--fail-on-increase` baseline the way `UNTYPED_BASELINE` was done; do not schedule a sweep |
| 10 import compat shims (`_compat_modules.py`) | file | Retire with ADR-0030 root-module freeze review; list them in the 12-09 packet |
| 667 Markdown files; constitution ≤ 12 enforced; archive tier manual | G5 row | Add an archive-growth signal (files per month) to the aging dashboard; no deletions |
| 963 commits since the last tag; version `0.1.0` | git | Cut a tag from the first green `main` (`v0.1.1`), run the release checklist in **counts-only** profile first; releasing is also the only way the Dependabot PRs get validated |
| 8 Dependabot PRs stalled since June/July | GitHub | After green: rebase and merge the GitHub Actions bumps (`setup-python` 6→7, `codeql-action`) first, then the uv-group bumps one at a time; close any that `uv lock` has already superseded (`pytest` 9.1.1 is already in use locally) |
| 30 `skip` markers, 0 `xfail` | grep | Fine. Keep the `undocumented_skip` audit flag at zero. |

### 3.5 F5 — What is working and must not be re-litigated

- MCP server governance (`tools/call` through `ApprovalPolicy`, hash-chained `mcp-<hex>.jsonl`, JSON-RPC `-32001`) landed 2026-09-24; verification-map oracles A5/A6 flipped from `known_failing` to `expected_pass`.
- EFX-001–003 runtime guards and providerless acceptance exist; the only open item is owner-authorized live proof, which this plan keeps **held** exactly as the execution plan §5 states.
- G6 (typed tests, zero audit flags) is complete and the `--fail-on untyped` ratchet is absolute. Do not reopen.
- The DR-006 gate trailer is mechanically enforced and green on history.
- Base-lockfile CVEs were resolved on 2026-09-29/30 (`cryptography`, `anyio`, `pyasn1`).

## 4. Proposed roadmap (dated, gated, falsifiable)

Status taxonomy follows [document-state-model.md](../governance/document-state-model.md); every row is `Proposed` here.

### Phase 0 — Restore green and record truth (target: by 2026-10-17; agent-completable; `fix:` and docs, no DR-006 trailer needed because no `feat:` touches `teaagent/`)

| ID | Work | Acceptance | Falsifier |
| --- | --- | --- | --- |
| R0-1 | `fetch-depth: 0` on `test` and `acceptance-all` checkouts | Failures #1–#6 disappear on the next `main` run | Any of #1–#6 still fails with full history |
| R0-2 | Shallow-clone skips for the five history-dependent tests | The tests skip (not fail) in a `--depth 50` clone and pass in a full one | A contributor's shallow clone still fails |
| R0-3 | `test_real_delivery_ledger_passes`: fixture ledger or explicit skip | Passes in a fresh clone with no `.teaagent/` | Still depends on gitignored state |
| R0-4 | `git init -b main` (or read the created branch) in `test_g2_g3_g22_focused.py` | Passes with `init.defaultBranch` unset | Fails on a runner with `master` default |
| R0-5 | Fix #9: test command `rg` → `grep`; receipt renders failed/unknown command outcomes | Test passes with `rg` absent from `PATH`; a `tool_call_failed` command shows `[failed: …]` in the receipt and never `[exit ` | Passes only after an assertion was relaxed, or a never-run command still renders silently |
| R0-6 | Rewrite the CI debt register to the §3.1 table | Register cites test names and causes, no "runner termination" wording without a log reference | Register still says "not reproduced off-runner" |
| R0-7 | `run_acceptance_tier.py` uses `sys.executable` | Tier runner uses the interpreter that launched it | — |
| R0-8 | Tag `v0.1.1` from the first green `main`; counts-only release evidence first | Tag exists; `release-checklist.md` T5 split gate followed | Tag cut from a red commit |

Order: R0-1 → R0-4 → R0-3 → R0-2 → R0-6 → R0-7 (one PR), then R0-5 (separate, may need iteration), then R0-8.

### Phase 1 — Owner decisions that are already due (target: by 2026-10-24; owner-only; agents prepare packets)

| ID | Decision | Default if the owner records nothing | Packet agents can prepare |
| --- | --- | --- | --- |
| R1-1 | ADR-0031 disposition | **Revert** (per ADR text and the 2026-08-31 advisor); alternative: one bounded extension to ≤ 2026-11-15 tied to a booked B1 session | Refreshed `build_h4_decision_packet.py` output for window ending 2026-10-09; the revert plan is written only after the owner chooses revert (execution plan §6.2 forbids pre-building) |
| R1-2 | DR-006 falsifier review record (F1 green, F2–F4 unexercised) | Record "reviewed, no violation, F2–F4 unexercised" in DR-006 | Draft paragraph; `check_dr006_gate_trailer.py --base 3ff0fa24` output |
| R1-3 | T5 quarterly survey: run (docs-only hypothesis intake) or record an explicit skip | Explicit skip with reason | `refresh_competitive_docs.py` dry run; list of survey sources |
| R1-4 | Validate or reject the three agent-verified open hypotheses in the friction log | Stay open | Already prepared (2026-09-14 closure evidence) |

### Phase 2 — One owner-observed coding session (target: a booked date before 2026-11-15; owner-only; `owner-override: co-maintainer dogfood`)

This is R4 from the 2026-09-16 rethink, unchanged: one real coding task through `teaagent agent run` (or TUI) with actual tool activity, approval/rejection, receipt inspection and undo, recorded by the owner in `docs/work-log/`. Agents prepare the scratch scenario and collect B2 evidence; the owner writes the testimony, the friction entries (or an explicit "no friction"), and the D1 verdict. It is the **only** lane that can produce organic `h4_governance_shadow` receipts, G1 evidence, and new friction. If the owner cannot book it, say so in R1-1 and let revert happen; a harness with zero recorded friction and zero recorded use is **done for now, not stalled**.

### Phase 3 — ADR-0043 quarantine disposition (2026-12-09; owner decision; agents prepare the ADR-0029-style packet)

| Surface | Prepared evidence | Default disposition |
| --- | --- | --- |
| `teaagent/domain/workflow_engine.py` + root shim + `skills/builtin/workflow-orchestration/SKILL.md` | 0 production callers (sweep 2026-09-13) | **Delete**; amend ADR-0041's five-module scope in the same change |
| `teaagent/consensus/` + CLI handler | default-off; G34 shows the CLI path never sees peers | Delete per ADR-0029 precedent unless `owner-override` |
| `teaagent/federated_sync.py`, `teaagent/signature_relay.py` | opt-in only | Delete together unless multisig is ratified |
| `teaagent/anp_adapter.py` | stub run path; tests only | Delete unless `owner-override` |
| `teaagent/jit_approval_server.py` | M4 carve-out | Keep only if Phase 2 happened and used it; else delete |
| ADR-0007/0019/0020/0021 status lines | contradict ADR-0043 | Amend to "Superseded in part by ADR-0043" in the same packet |

Packet contents (prepare in November): per-surface import-graph proof, LOC and test counts to be removed, git recovery anchor, and the consistency-guard changes (`check_root_module_count.py` ceiling lowers accordingly). Expected effect if all defaults are taken (measured on this tree with `wc -l`): **4,920 lines** across the eight listed `teaagent/` files leave the tree, plus the test files that pin them (11,622 lines across files that reference those modules; some of those files also cover other behavior and would shrink rather than disappear). That would be the first **measured** thinning since the harness-first decision. Do not pre-delete.

### Phase 4 — Trigger-only lanes (unchanged from the execution plan §7)

EFX live proof (owner authorization), H2 continuity, H3 ecosystem trust, H5/M5 eval, H6/M6 packaging, WDH-002, EFX-FUTURE: no planning work until their named trigger fires. This review found no new trigger evidence for any of them.

### Continuous ratchets (no owner decision needed; `governance-gap` or `fix:`)

- `Any` baseline with `--fail-on-increase`.
- God-module exemption count may only decrease; next candidate `cli/_agent_parsers.py` (A-P2-2).
- Archive-tier growth per month on the aging dashboard.
- Test-job wall-time soft budget 20 minutes.
- Dependabot: merge within two weeks of green, one PR per CI cycle.

## 5. Critical thinking check

1. **Assumption audit.** (a) The CI logs I read are the current failure set — true for run 858; a later push could change it. (b) `fetch-depth: 0` is acceptable cost on the `test` matrix (the repo is 1,428 commits; clone cost is seconds) — if the owner objects, the alternative is making the six tests skip on shallow clones, which R0-2 already proposes. (c) The owner still wants harness-first — every authority doc says so and nothing since contradicts it. If (c) fails, Phases 1–3 change entirely.
2. **Evidence check.** *Fact:* 8/9 failures reproduce off-runner; 2/9 with full history; `.teaagent/` is gitignored; ADR-0031 has no post-09-29 entry. *Inference, later falsified:* #9 was first attributed to a first-run/HOME interaction; the reproduced cause is a missing `rg` executable plus a receipt builder that drops `tool_call_failed`. *Assumption:* no owner decision exists outside the repository (an un-committed local note would change F2). *Value judgment:* revert is the better default for ADR-0031; the owner may legitimately weigh optionality higher.
3. **Counterargument (steelmanned).** "Green CI and overdue paperwork are housekeeping; the real problem is that the harness has no users, so spend the quarter on usability." Response: usability work without owner evidence is exactly what DR-006 forbids and what the 2026-06-13 direction retired; and red CI silently blocks every other lane (Dependabot, releases, the gates that make claims trustworthy). Housekeeping first is the cheaper way to make the usability question answerable.
4. **Fallacy scan.** The register's "runner termination" explanation was a correlation (failures only on remote runners) read as a cause; the logs show deterministic test failures. This review avoided the mirror error at first by leaving #9 **unexplained** rather than attributing it to the shallow-clone cause; the later reproduction (missing `rg`) confirmed it was a distinct cause. "Zero organic runs" is not read as "zero demand" (the 2026-09-16 rethink §3.4 rule).
5. **Falsifiability.** This plan is wrong if: the next `main` run after R0-1…R0-4 still fails on tests other than #9; or the owner produces a dated ADR-0031 disposition made before 2026-10-09 that the repo does not contain; or the owner books and completes Phase 2 and it yields organic events plus friction, in which case Phase 3's default-delete posture for `jit_approval_server.py` and the M4 carve-out must be re-scored on that evidence.

## 6. Owner asks (one line each; default applies if unanswered by 2026-10-24)

1. Approve Phase 0 as `fix:` work on existing contracts (default: proceed; it touches CI config and tests only).
2. ADR-0031: revert, or extend to a date ≤ 2026-11-15 with a booked B1 session (default: revert).
3. Book the Phase 2 session date, or state that none will be booked this quarter (default: none → ADR-0031 revert stands, Phase 3 defaults stand).
4. Record the DR-006 falsifier review and the T5 survey decision (default: "reviewed, no violation" and "skipped Q3, docs-only").
5. Confirm the Phase 3 default dispositions may be **prepared** (not executed) in November (default: prepare).
6. Confirm `v0.1.1` may be tagged from the first green `main` (default: tag).

## 7. Do not do (carried forward, restated for this plan)

- Do not treat this record as adoption, as a `Gate: owner-override`, or as owner testimony.
- Do not weaken, skip, or delete a test to get green: R0-2/R0-3 convert environment-dependent **false failures** into explicit skips with a stated reason, and keep every synthetic-fixture validator test.
- Do not flip any `shadow` mode, use live credentials, or delete a quarantined surface on this review's authority.
- Do not open a new strategy document for the same question; amend this one or the authority docs.
- Do not relabel agent or fixture runs as owner runs, and do not turn unknown provenance into either use or disuse.

## 8. Verification of this record

Documentation-only. Validation for the recording commit: `bash scripts/verify_docs.sh` (inventory, aging, snippet inventory, release docs bundle, OKF bundles, docs consistency) must pass; `docs/INDEX.md` lists this file under Evidence And Review; `docs/roadmap-status.md` carries a one-line dated review note stating that no horizon, milestone, or gate status moved; the action register carries G-P2-21.
