# Roadmap Status

> **Claim class:** Current truth for roadmap horizon, milestone, and track status.
>
> **Owns:** Which workstreams are complete, in progress, or pending, and their
> next gates.
>
> **Does not own:** Daily-user command recommendations (`daily-driver-current-status.md`)
> or historical review reasoning in dated analysis files.
>
> **Last reviewed:** 2026-09-14

**Last updated:** 2026-09-09 (Socratic roadmap/intent panel, 7 lenses, record [reviews/roadmap-intent-socratic-2026-09-09.md](reviews/roadmap-intent-socratic-2026-09-09.md); owner adopted all 10 ledger items. Corrections landed: G1/G3/G4/G5/G6 rows restated from `Complete`/`Pending` to their evidenced state; ADR-0031 criterion 1 restated as **unexercised, not clean** — `scripts/prepare_h4_evidence.py` now reports a reachability denominator and a `verdict`, and for the 2026-08-13→2026-09-11 window it returns `unexercised` with **0 observed / 0 reachable runs**; across all recorded history only **4 of 415 runs** ever reached an H4 surface at all, because `.teaagent/runs/runs-index.jsonl` holds just 6 distinct synthetic benchmark/smoke prompts and **zero organic owner tasks**, so `0 observed` carries no information about false-positive rate; criterion 2 passes **vacuously** (0 workspace policies, 0 roles, 0 declarations); `promotion_ready` is a hardcoded literal in `teaagent/governance/h4_decision_packet.py`, not an evaluated metric; criterion 4 remains human sign-off. Promotion on 2026-09-12 is arithmetically unreachable — only `extend` (valid only with a dated dogfood session booked) or `revert`. Synthetic demo receipts are now stamped `provenance='synthetic-demo'` and excluded from candidates, so the "demo synthetic ≠ C1" rule is code-enforced rather than prose-only. EFX-001–003 remain In Progress with live-provider proof pending. The owner-operator remains the **target** persona; active operational validation is unevidenced in the run store. Per harness-first §4.2 raw suite counts are not quality claims; DR-006 gate citation is now enforced by `scripts/check_dr006_gate_trailer.py`, and non-goal surfaces are quarantined under [ADR-0043](adr/0043-legacy-competitive-surface-quarantine.md))

**Review 2026-09-12 (ADR-0031 expiry day):** decision window closed 2026-09-11 with verdict `unexercised` (0 observed / 0 reachable, re-verified today); no dogfood session booked, zero new runs (latest run 2026-08-31) and zero new friction entries — promotion unreachable, decision is the owner's today (extend-with-booked-session or revert). Falsifier-1 now mechanical via `check_dr006_gate_trailer.py`: 8 post-DR-006 `feat` commits touching `teaagent/`, 1 cites a gate (`87d1c61`); retrospective only, the gate landed 2026-09-09. DR-006 falsifier window closes 2026-09-22. No horizon or milestone status moved by this review.
**Update 2026-09-12 (goals-review instruments):** the 5-lens goals Socratic panel (record `.teaagent/reviews/goals-socratic-2026-09-12/synthesis-record.md`, gitignored) ruled the goal set directionally right but badly measured; owner approved the instrument items. Landed: `scripts/prepare_g1_evidence.py` (G1 denominator+verdict, `unexercised` today), G2 one-screen acceptance test, G6 `untyped` classification + `--fail-on untyped` ratchet (458 untyped), G5 corpus-cost section in the aging dashboard, and `origin` on `run_started`/runs-index (B-08; `TEAAGENT_RUN_ORIGIN` or `run_started_extra`, default `unknown`). Goal-text items (B-05/B-07/B-10), deletions (B-06/B-09), and B-11 remain owner-gated.
**Update 2026-09-13 (agentflow v8.2.0 survey delta + AGF-001 implementation + gated-items panel):** re-surveyed `agfnow/agentflow` at `fcb6878` (v8.2.0); AGF-001 `teaagent skill audit` landed under owner "implement governance gaps" direction; AGF-002 verified already present. A 5-lens Socratic panel re-verified every owner gate (record `.teaagent/reviews/gated-items-2026-09-13/synthesis-record.md`, gitignored): **all gates hold**; corrections landed — EFX exit-evidence narrowed to the falsifiable residual (one real provider mutation observed to behave as classified), workflow_engine importer sweep recorded complete (0 production callers), DR-006 falsifier retrospective prepared (10 post-DR-006 feats, 3 gate-cited, 0 violations post-mechanization; F2–F4 unexercised). **ADR-0031 is actively decaying**: criterion 1 is unreachable at zero organic traffic, so "no decision" produces the permanent-shadow anti-pattern the ADR forbids — highest-value owner ask is booking one M4 dogfood session. Ungated lane found: G6 untyped ratchet (458→0). No horizon, milestone, goal, or EFX status moved.
**Update 2026-09-13 (vendor direction survey):** surveyed OpenAI (Agents API, managed cloud agents, 3.1 agent-workdays/human-day internally), Anthropic (Trustworthy Agents framework — harness as security boundary, Plan Mode oversight, prompt-injection defense-in-depth), and DeepMind (AI Control Roadmap — insider-threat framing, supervisor monitoring, coverage/recall/response-time metrics, 1M coding-agent trajectories analyzed). Conclusion: vendor convergence **validates** harness-first; the one substantive gap is live monitoring → VND-001 (Proposed), plus VND-002 threat-model docs addition (Proposed) and VND-003 autonomy metrics (On Hold — zero organic runs). Record `.teaagent/reviews/vendor-directions-2026-09-13/survey-record.md` (gitignored). No status moved.
**Update 2026-09-13 (G6 untyped ratchet zeroed):** all 458 untyped test files classified via `# test-type:` markers (12-agent parallel pass; 455 behavior / 82 contract / 39 adversarial / 31 lifecycle totals); `UNTYPED_BASELINE` lowered 458→0 — the CI `--fail-on untyped` gate is now absolute. G6 stays Partial: 71 construction-only / 5 high-risk files remain (assertion-strengthening lane, not typing). No other status moved.
**Update 2026-09-13 (G6 P0 flags cleared):** strengthened all 5 P0-tier flagged test files — `test_audit.py` (14 construction-only + 1 permanently-skipped placeholder → real `RecursionError` test), `test_managed_runtime_audit.py`, and 3 security acceptance flows (read-only gate, vote relay, approval manager). `high_risk_files: 0`; `construction_only` residual is now 66 files, all lower-tier. `test_verify_valid_chain` renamed `test_verify_chain_detects_tampered_hashes` — the old name claimed validity while the fixture used dummy hashes.
**Update 2026-09-13 (G6 construction-only residual cleared + stale contract fixed):** 9-agent parallel pass strengthened all 66 remaining `construction_only` files — every assert verified against probed runtime behavior; several tests were asserting wrong behavior and were corrected (e.g. `test_production_warnings_are_strings` was vacuous on this platform; `test_cli_with_special_characters_in_api_key` asserted success where a NUL byte forces exit 1). Also fixed a **pre-existing failure**: `test_m1_audit_stream_matches_frozen_contract` was red on clean tree — the `origin` field (B-08, landed `338de3a8`) was missing from the golden contract; updated. `construction_only_files: 0`, `high_risk_files: 0`, `placeholder_files: 0`. G6 → **Met**.
**Update 2026-09-13 (G6 zero-flag):** 9-agent parallel pass fixed all 36 remaining flagged files — 33 `no_assertions` (call-and-pray tests now assert probed outcomes), 2 `assert_true` (one was dead code in an unreachable branch; one masked a real `TypeError`), 2 `undocumented_skip` (positional skip message → `reason=` keyword). Several tests were exercising nothing real and were corrected (e.g. `test_n4_git_transaction_sink_records_file_writes` never created a commit — no file changes meant 'nothing to commit'). Audit is fully clean: zero flags of any kind.
**Review 2026-09-14 (hygiene + overdue-decision flag):** re-ran the §3.5 starts-now lane — `prepare_h4_evidence.py` still `unexercised` (0 observed / 0 reachable / 5732 total events); `test_efx*` 15/15 pass. Found and fixed a **date-bomb**: `test_h4_shadow_demo.py` + `scripts/exercise_h4_shadow_demo.py` hardcoded `until='2026-09-11'` (the ADR-0031 window close), so the demo's own events fell outside the window and `synthetic_excluded` read 0 — test went red on 2026-09-12. Both now use `until=date.today()` (`791eb1bc`). Friction-log evidence attached to the 3 open hypotheses (`d7308906`); closure itself is owner-only per `scripts/validate_docs_consistency.py`. **ADR-0031 owner decision is now 2 days overdue** (review date 2026-09-12); the permanent-shadow decay the gated-items panel flagged is active. No horizon or milestone status moved by this review.
**Update 2026-09-14 (VND-002 insider-threat docs):** owner authorized the docs-only VND-002 item via the "implement tasks" direction; added the insider-threat/agent-misalignment class to `docs/threat-model.md` — a new threat-table row plus a dedicated section citing DeepMind's AI Control insider-threat framing and the ~1M-trajectory finding that most flagged events are misinterpretation/overeagerness, not adversarial intent. VND-002 → Complete. VND-001 (live supervisor) and VND-003 (autonomy metrics) remain owner-gated. No other status moved.
**Update 2026-09-14 (ADR-0031 extension + VND-001 authorization):** owner decided ADR-0031 → **extend with a booked co-maintainer dogfood session** (not revert). The extension is conditioned on the session being scheduled — a new decision-window close is set when the session date lands, so the shadow does not decay open-ended; `promotion_ready` stays `false` and criterion-1 `owner_verdict` remains owner-only. Owner also authorized **VND-001** (live supervisor / post-run trajectory reviewer) under the `governance-gap` DR-006 gate; implemented as `teaagent/run_review.py` + `teaagent runs review <run_id>` (post-run reviewer; in-run monitor remains future). No horizon/milestone status moved by this record.
**Update 2026-09-14 (dogfood session booked):** owner scheduled the co-maintainer dogfood session for **2026-09-15** (scope: background lifecycle + operator cockpit per DR-006 T4; cloud/gateway/multi-tenant held). Recorded as `docs/work-log/m4-dogfood-2026-09-15.md` — the dated owner-override entry gate for Horizon B and the ADR-0031 extension condition. New ADR-0031 decision-window close = **2026-09-15**; after the session, agents run B2/B3 (`prepare_h4_evidence.py --until 2026-09-15`, `build_h4_decision_packet.py`, BG-001/cockpit specs) against the real audit logs. No horizon/milestone status moved by this record.
**Update 2026-09-15 (ADR-0031 evidence: approval surface wired + first organic events):** found and fixed a wiring gap — `AgentRunner` in `chat_agent.py` was built without `workspace_root`, so `RunnerApprovalCoordinator.workspace_root` stayed `None` and `evaluate_approval_policy_shadow` early-returned before recording `h4_governance_shadow`; the **approval surface was unreachable on the main `agent run` path** (only subagent launches, which pass `self._root`, ever emitted a receipt — the 4/415). Fix `8fd7a461` passes `config.root`. Two dogfood runs (`TEAAGENT_RUN_ORIGIN=dogfood`, fake provider) then produced the first **organic** `h4_governance_shadow` events: `surface=approval` `allowed=true` `enforced=false` (prompt mode + `workspace_write_file`), and `surface=subagent_launch` `allowed=false` `enforced=false` — a **denial candidate** (RBAC `start_workflow` denied yet the subagent ran in shadow mode) flagged for owner adjudication, not agent verdict. `prepare_h4_evidence.py` regenerated: verdict `unexercised` → `needs_review`, 2 observed / 9 reachable runs / 1 denial candidate; `promotion_ready` stays `false`. No horizon/milestone status moved by this record.
**Update 2026-09-15 (ADR-0031 evidence broadened + residual gaps):** continued dogfooding produced 3 more organic `approval` receipts (`workspace_apply_patch`, `workspace_run_shell_mutate`, `workspace_edit_at_hash` — all `allowed=true`, `provenance=null`). Packet regenerated `--until 2026-09-15`: **5 observed / 12 reachable runs / 1 denial candidate**; coverage now `approval` 4 (0 denials) + `subagent_launch` 1 (1 denial). Two residual gaps recorded for owner adjudication, not fixed: **(a) empty RBAC role store** — `.teaagent/roles/` + `.teaagent/role-assignments/` are empty, so `check_action_permission` returns "no role with permission `start_workflow`" for *every* subagent launch; harmless in shadow mode (`check_subagent_launch_rbac` returns `True` regardless) but if `rbac_governance_mode` ever flips to `enforce`, all subagent launches break — needs a bootstrap/default-role decision. **(b) ANP adapter dead surface** — `teaagent/anp_adapter.py:364` builds `AgentRunner` without `workspace_root` and `ANPBidirectionalAdapter` has no root attribute; wiring it needs a constructor param plumbed through callers (secondary surface, out of `agent run` scope). `promotion_ready` stays `false`; `owner_verdict` untouched. No horizon/milestone status moved by this record.
**Update 2026-09-15 (VND-001 reviewer fix + third residual gap):** dogfooded `teaagent runs review` on the new runs and found a coverage bug — `review_run` only counted `tool_call_started`, but a call paused at the approval gate emits `tool_call_pending_approval` and never reaches `tool_call_started`, so blocked capability requests (the exact `unapproved_capability`/`denied_attempt` signals) were invisible (`tool_calls=0`, `coverage=0.0`). Fix `ec7656e3` counts `tool_call_pending_approval` as a call (deduped by `call_id`); verified `tool_calls 0→1`, `coverage 0.0→1.0`. Third residual gap recorded for owner adjudication: **subagent_launch allow path is unreachable by design** — `assignee` always falls back to `parent_run_id` (a fresh id per run; `operator_id`/`agent_id` are not real `ChatAgentConfig` fields), and `get_roles_for_assignee` has no wildcard/default role, so `start_workflow` can never be granted to a stable identity. The RBAC check is therefore structurally deny-only until a stable operator identity exists. `promotion_ready` stays `false`. No horizon/milestone status moved by this record.
**Update 2026-09-15 (approval-shadow observation bias + allow-mode run):** drove an `allow`-mode run — the destructive call completed the full lifecycle (`tool_call_requested`/`started`/`completed`, file written) but emitted **no** `h4_governance_shadow`. Fourth residual gap recorded for owner adjudication: **the approval shadow only observes prompt-mode runs** — `evaluate_approval_policy_shadow` is invoked inside `handle_approval_request`, which only runs when `can_request_approval` is true (PROMPT mode + destructive). In `allow`/`workspace-write`/`read-only` modes the shadow never fires, so H4 evidence is systematically biased toward prompt-mode runs and blind to the modes where enforcement matters most. Whether the shadow should observe every destructive call regardless of mode is a semantic boundary (observation scope + audit volume), so recorded not fixed. Packet regenerated: 5 observed / 13 reachable runs / 1 denial candidate. `promotion_ready` stays `false`. No horizon/milestone status moved by this record.
**Update 2026-09-15 (observability + lifecycle surfaces verified):** exercised the H4 control-plane/audit surfaces on the dogfood runs — all healthy. `agent resume` completed the pending→resume→auto-approve→complete lifecycle (`auto_approved_call_id` recorded; consistent with the observation-bias finding, no `tool_call_approved`/shadow on the auto-approve path). `audit verify` reports **VALID hash chain** on all 7 dogfood runs (zero gaps/modifications/insertions). `runs export` (completeness `ok:true`, full trace), `runs replay` (dry-run, `tools_used`), `cockpit` (`pending_count:6`, `quarantine_count:28`, context health green), `daily` (flags pending approvals), and `runs list` all work. `origin: dogfood` correctly recorded in `runs-index.jsonl` (B-08) — owner can cleanly filter dogfood vs organic runs. `memory_write_quarantined` fired correctly (provenance gate quarantined the subagent's auto-curated memory write). No new gaps; these surfaces are healthy. `promotion_ready` stays `false`. No horizon/milestone status moved by this record.
**Update 2026-09-15 (approval lifecycle completed + provenance fix):** resolved all 6 pending approvals via `teaagent approval approve` — the canonical `tool_call_pending_approval`→`tool_call_approved` lifecycle now exercised organically on 8 runs. Found and fixed a provenance gap (`2f144102`): the CLI approve path recorded `tool_call_approved` with only `call_id`/`tool_name` — no `authority_type`/`approved_by` — so CLI-approved calls were indistinguishable from JIT-prompt approvals in the audit trail. Now records `authority_type='cli_approval'`, `approved_by='operator'` (consistent with `jit_prompt`/`auto_mode`/`preapproved_payload_digest`); verified on a dogfood run. `promotion_ready` stays `false`. No horizon/milestone status moved by this record.
**Update 2026-09-15 (deny-preset enforcement gap — most serious finding):** exercised the deny path and found a documented safety control that is **advisory-only at runtime**. `teaagent approval deny <tool>` registers a deny grant and `approval check`/`explain` correctly report `decision: deny` ("Matching deny grants block the tool call"), but the runtime path never blocks: `assert_allowed` → `check_preset` → `is_allowed`, which collapses `deny` and `prompt` both to `False`, so a matched deny grant is indistinguishable from "no preset" and falls through to `pending_approval` (prompt mode) or executes (allow mode). Verified: a scoped deny preset on `workspace_run_shell_mutate` did NOT block the matching call in either mode. Root cause: `check_preset` returns a bare bool that can't distinguish deny from no-match; `_resolve_decision` already exposes `decision` distinctly but the runtime path doesn't use it. **Not fixed** — enforcement change on `teaagent/approval/manager.py` (high-risk path) that alters when calls block; needs a risk report + owner sign-off. Test preset revoked. `promotion_ready` stays `false`. No horizon/milestone status moved by this record.
**Update 2026-09-15 (budget + plan-gate + sandbox boundaries verified):** exercised the remaining governance boundaries — all enforced correctly. **Budget**: `max_tool_calls=1` → `run_failed: tool-call budget exceeded` after exactly 1 call; `max_iterations=1` → `run_failed: iteration budget exceeded`; both with actionable messages. **Plan gate**: `run --from-plan <plan> --require-plan` blocked `workspace_write_file` with `tool_call_blocked`/`authority_type: policy_blocked` — "Intent drift: target outside the approved plan scope" (the write target wasn't in the plan's declared files). Intent-drift enforcement works. **Git sandbox**: `git_sandbox_started` fires per run; headless runs keep the `teaagent-sandbox-<run_id>` branch for review and restore the tree (deliberate, not a bug) — but branches accumulate with no auto-prune (27 now; manual via doctor/experiment only), a minor housekeeping note. `promotion_ready` stays `false`. No horizon/milestone status moved by this record.
**Update 2026-09-15 (undo/rollback data-loss hazard — second serious finding):** exercised `teaagent undo` and found a destructive edge. `undo --preview` diffs `sandbox_branch → original_branch`, but `original_branch` (main) has moved forward since the run, so the preview shows **all later commits**, not just the run's writes — misleading. Worse, `GitBranchSandbox.rollback()` runs `git reset --hard HEAD` + `git clean -fd` **before** checkout, assuming HEAD is on the sandbox branch; but after a headless run `keep()` already restored `main`, so `undo` on a completed run would `reset --hard` + `clean -fd` **on `main` itself** — wiping uncommitted work — then `branch -D` the kept review branch. Verified by code read (`teaagent/sandbox/_git_branch.py:254-280`) + preview behavior; not executed (would destroy the working tree). **Not fixed** — `teaagent/sandbox/` is a high-risk path and the fix (guard rollback to only run on the sandbox branch, or scope the reset) changes destructive behavior; needs a risk report + owner sign-off. `promotion_ready` stays `false`. No horizon/milestone status moved by this record.
**Update 2026-09-15 (attach-resume provider gap):** exercised `agent attach <run_id> --resume` on a pending run — it failed `run_failed: opencodezen-go requires OPENCODEZEN_API_KEY`. `attach` has no `--provider` flag and resumes with the configured default provider, not the original run's provider, so `attach --resume` **cannot resume any non-default-provider run** (it errors on credentials). `agent resume <provider> <run_id>` works (takes provider positionally). Recorded as a gap — the attach-resume path should inherit the run's recorded provider. `promotion_ready` stays `false`. No horizon/milestone status moved by this record.
**Update 2026-09-15 (session/background durable-continuity verified):** exercised the H4 durable run-state surfaces — all healthy. `session list` shows per-run heartbeat + `git_sandbox` state + status; `background list` shows background-task lifecycle (pid, log, exit_code, run_id). `session resume <run_id> fake` resumed a pending run, auto-approved the call, and attempted it (failed only on the probe's intentional bad hash — the resume path itself is correct). `origin: dogfood` attributed throughout. No new gaps. `promotion_ready` stays `false`. No horizon/milestone status moved by this record.
**Update 2026-09-15 (diagnostics verified; doctor-all false-negative noted):** ran the harness's own diagnostics — `doctor project` 9/9 security checks green (`.teaagent/` mode/ownership, secret mode/content), `selftest` all green (audit completeness, permission smoke "read-only blocks destructive write", tool lint 0 errors). `doctor all` reports `ok: False` but only because 11/14 providers lack API keys (expected — only `fake` is configured); the overall `ok` flag counts unconfigured optional providers as failure, a false-negative signal worth noting (an operator reading `ok:False` can't tell "no providers configured" from "something broken"). `promotion_ready` stays `false`. No horizon/milestone status moved by this record.
**Update 2026-09-15 (watch verified; interactive-only boundary reached):** `teaagent watch` works — polls and reports `pending=N` + run status each interval. `agent interactive-review` requires `suspension-<run_id>.json`, which is only written by `suspend_to_background` from the interactive REPL — not reachable headless, so that surface stays unexercised (it's the one path that genuinely needs a TTY/owner session). This completes the non-interactive surface coverage: every headless-reachable governance boundary, lifecycle path, observability tool, durable-continuity surface, and self-diagnostic has now been exercised. `promotion_ready` stays `false`. No horizon/milestone status moved by this record.
**Update 2026-09-15 (interactive-review exercised — full surface coverage):** drove `agent interactive-review` by writing a `suspension-<run_id>.json` in the `suspend_to_background` format plus a tracked change — the review header, changed-file list, per-file diff, and the `y`/`e`/`r`/`n`/`q` action loop all work (probe artifacts cleaned up). This completes surface coverage: **every** governance boundary, lifecycle path, observability tool, durable-continuity surface, self-diagnostic, and the interactive review loop has now been exercised. Final tally: 3 bugs fixed (`workspace_root` wiring, reviewer blocked-call coverage, CLI approval provenance), 7 gaps + 1 denial candidate recorded for owner adjudication (2 safety-critical: deny presets advisory-only, undo resets `main`). `promotion_ready` stays `false`. No horizon/milestone status moved by this record.
**Update 2026-09-15 (MCP server + skill audit verified):** exercised the two remaining surfaces. `teaagent mcp serve` over stdio JSON-RPC — `initialize` returns `teaagent` with `tools` capability, `tools/list` returns 23 workspace tools, `tools/call workspace_git_status` executes and returns clean status (full external-agent consumption path works). `teaagent skill audit` (AGF-001) — 268 skills across roots, 49 name collisions, `status: ok`, `issues: []`, `assessment: not_performed` (semantic conflict assessment is documented as out-of-scope for the command). No new gaps. `promotion_ready` stays `false`. No horizon/milestone status moved by this record.















**Prior update:** 2026-08-31 (advisor: H4 extend only if dogfood scheduled for organic events else revert, 0 organic ≠ promotion, demo synthetic ≠ C1; EFX promote only on live proof; M4 dogfood is the only DR-006 lane that can generate organic events/friction/BG-001. Suite observation at `bf07bc8`: `6681 passed, 0 failed, 26 skipped` via sharded `pytest -n auto --dist worksteal`, 6707 collected — recorded as a historical observation only, **not** a quality claim, per harness-first §4.2; see [suite truncation analysis](analysis/suite-truncation-root-cause-2026-06-10.md))

> **Canonical source of truth.** All other status docs (`docs/security/risk-register-and-threat-model-2026-06-02.md`, `docs/analysis/defeat-scenarios-and-cascade-effects-2026-06-02.md`, `docs/analysis/active-findings-status-ledger-2026-06-06.md`) defer to this document for overall completion status. Per-item test evidence lives in the risk register §9.

> **Direction note, 2026-06-14.** Roadmap rows describe owner-operator harness work unless explicitly labeled future or aspirational. External adoption, hosted deployment, enterprise/team operations, and broad daily-driver claims are not current goals.

## Purpose

Provide a single source of truth for roadmap item status, ownership, confidence, and next gates. Every roadmap item should have exactly one owner surface and status.

## Scheduling Rule

As of 2026-08-26, EFX-001 through EFX-003 are the only newly known,
authorized, non-held code items. They entered through DR-006's
`governance-gap` lane after deterministic local probes reproduced ambiguous
mutating-tool dispatch, effectful-tool approval bypass, and reusable
argument-blind one-time approval. Runtime guards now exist on the existing
runner, registry, audit, and approval seams with focused tests and providerless
acceptance (`tests/acceptance/test_efx_durable_effect_flow.py`); live
GitHub/browser/provider proof is still required before Complete. They do not authorize an effect
platform, exactly-once claim, distributed outbox, fencing service, actor
supervisor, or second event/workflow framework.

H0-H6 remain status taxonomy, not sprint menus. Other new work starts only from
cited owner friction, an independently proved governance gap, a dated owner
override, qualifying M4 co-maintainer dogfood, or the existing
[dated decision queue](specs/held-roadmap-forward-spec-index-2026-07-11.md#8-dated-decision-queue).
A trigger opens evaluation outside the proved governance-gap lane; it does not create implementation authority or prove completion.

## Roadmap Horizons

| Horizon | Name | Target Outcome | Owner | Status | Confidence | Next Gate | Exit Evidence |
|---------|------|----------------|-------|--------|------------|-----------|---------------|
| H0 | Claim and risk hygiene | Public claims, risk register, docs gates, and tool warnings are owned | governance | Complete | High | H1 | H0 exit evidence met; all M0 checks pass |
| H1 | Daily operator loop | Setup, daily cockpit, plan, execute, approve, verify, recover, and remember are one coherent journey | governance | Complete | High | H2 | Journey acceptance tests pass across CLI/TUI baseline; acceptance tier snapshot `628 passed` at `85109e4` (2026-06-10) |
| H2 | Multi-surface continuity | CLI, TUI, IDE, dashboard, background, cloud, and gateway share one run-state contract | TBD | On Hold — M2 foundation complete | Medium | Owner-validated continuity need | M2 acceptance complete; full surface parity (IDE/dashboard/cloud) is external/future under harness-first |
| H4 | Durable owner/agent operations | Long-running owner-operator and co-maintainer-agent workflows have durable run-state continuity, control-plane views, policy, audit, and cost attribution. Run continuity does not imply exactly-once tool execution, external-effect settlement, business acceptance, or reversal; ADR-0042 remains binding | TBD | On Hold — shadow wiring exists; ADR-0031 evidence packet prepared 2026-08-27, refreshed 2026-08-31 and re-verified 2026-09-12 over the closed decision window 2026-08-13→2026-09-11 (`prepare_h4_evidence.py --since 2026-08-13 --until 2026-09-11`: 0 observed / 0 reachable runs, verdict `unexercised`; `promotion_ready=false` is a hardcoded literal, not a metric); H4 demo `scripts/exercise_h4_shadow_demo.py` exercisable (2 synthetic candidates, must not launder into C1) and guarded (`tests/test_h4_shadow_demo.py`); 2026-09-12 expiry-day state: no dogfood session booked, zero new runs and zero new friction entries since review, so promotion is unreachable — owner decided 2026-09-14: extend with a booked co-maintainer dogfood session (new window close set on booking) | Low | Dogfood session booked 2026-09-15 (background+cockpit, docs/work-log/m4-dogfood-2026-09-15.md) — new ADR-0031 window close 2026-09-15; EFX live-proof closure remains pending owner authorization | Policy/RBAC shadow-wired (WDA-002/003); EFX-001–003 runtime guards landed on existing seams with live-provider proof pending; EFX live-proof procedure `docs/plans/efx-live-proof-procedure-2026-08-31.md` and H4 demo `scripts/exercise_h4_shadow_demo.py`/`tests/test_h4_shadow_demo.py` ready for owner auth; generic external-effect reconciliation remains held; ADR-0029 Option D executed; ADR-0031 evidence packet at `.teaagent/reviews/adr-0031/` (2026-08-27, refreshed 2026-08-31, re-verified 2026-09-12); advisor artifact `.omx/artifacts/claude-you-are-an-external-advisor-for-teaagent-a-harness-first-own-2026-08-31T06-14-02-585Z.md` |
| H6 | Owner packaging and local distribution | Desktop/client-server and local release channels have supply-chain, update, rollback, and support plans for owner-operated use | TBD | On Hold — local proof exists; daily CLI unwired | Low | Owner update friction + trust-boundary proof | Single-platform update proof is reproducible via `scripts/prove_update_platform.py`; `update/*` remains intentionally absent from the daily CLI; no desktop packaging/session-attach proof |

## North-Star Goals (G1-G6)

Owner-ratified harness goals from the
[Harness-First Direction](strategy/harness-first-direction-2026-06-13.md) §2.
This table owns their current honest status; the identity document keeps the
ratified wording. Adoption record:
[whole-project lens review](analysis/whole-project-lens-review-2026-08-26.md).

| Goal | Ratified outcome | Status | Evidence / gate |
| --- | --- | --- | --- |
| G1 | Daily task without consulting docs | Unmeasured — no organic evidence | Friction log 5/5 owner entries closed, but all 12 entries are dated 2026-06-22 and there have been zero new entries since; no doc-lookup metric exists; `.teaagent/runs/runs-index.jsonl` records 415 runs over 2026-06-03→2026-08-31 comprising only 6 distinct synthetic benchmark/smoke prompts and zero organic owner tasks (2026-09-09 audit). Absence of friction is dormancy evidence, not ergonomics evidence. `scripts/prepare_g1_evidence.py` (B-01, 2026-09-12) now reports the organic/synthetic denominator plus a `verdict` (`unexercised` today) so an empty log can no longer read as success |
| G2 | Any run explained from one artifact | Pending — Unmeasured (surface exists) | `teaagent agent show <run>` plus run evidence summary (`tests/acceptance/test_run_evidence_summary_flow.py`); one-screen acceptance now asserted by `test_run_receipt_answers_three_questions_within_one_screen` (B-02, 2026-09-12): why-allowed/what-changed/how-undo within `DEFAULT_PAGINATION_LINES` (50) |
| G3 | One event spine | Partial — rescoped by owner decision | M3 plan gate moved to a typed `RunEvent` spine interceptor cleanly; M4 approval/budget and M5 HookRegistry enforcement were assessed unsuitable for the spine/interceptor model and stay inline by owner-reviewed evidence (`docs/work-log/m4-budget-stays-inline-2026-06-13.md`, `docs/work-log/m5-hooks-observability-only-2026-06-13.md`). The spine's realized value is the observability read side, not wholesale relocation of mutating enforcement |
| G4 | Extensible by hooks, not forks | Partial — observability wired; enforcement bridge held | `HookRegistry` exists and emits typed audit events (`TOOL_HOOK_PRE_MUTATION`, `TOOL_HOOK_POST_MUTATION`, etc.) surfaced by the M2 reader; `tests/acceptance/test_hook_lifecycle_flow.py` passes. Pre/post tool hooks mutate in-flight args/results in `teaagent/tools.py`; moving enforcement to spine consumers is unsuitable (same runtime-coupling finding as M4). Six session-lifecycle hooks are defined but not wired to production callers — see `m5-hooks-observability-only-2026-06-13.md` |
| G5 | Docs corpus carries its weight | Partial — corpus cost signal live | `docs/generated/docs-aging-dashboard.md` `## Corpus Cost (G5 Signal)` reports total/live/archive counts and per-surface costs; `scripts/report_docs_aging.py` runs in CI. Current corpus: 646 Markdown files, 645 in `docs-inventory.md` (8 constitution, 369 working, 268 archive). Constitution-tier ≤ 12 claim-tested docs is not yet enforced; archive-tier discipline is manual, not automated |
| G6 | Tests prove behavior, not construction | **Complete — typing complete, ratchet absolute, zero flags** | 606 test files; all 458 backlog files classified 2026-09-13 (455 behavior / 82 contract / 39 adversarial / 31 lifecycle); `UNTYPED_BASELINE = 0` — `--fail-on untyped` in CI now fails on **any** new untyped file. All 71 `construction_only` + all 36 `no_assertions`/`assert_true`/`undocumented_skip` files strengthened 2026-09-13 (every assert verified against probed runtime behavior). Audit fully clean: `high_risk_files: 0`, `medium_risk_files: 0`, `construction_only_files: 0`, `placeholder_files: 0`. Raw suite counts are not a quality claim per harness-first §4.2 |

## Roadmap-Neutral Governance-Gap Intake - Effect Authority

These items do not reopen or renumber H0-H6. `Promote` is the scheduling
disposition under DR-006; implementation status is `In Progress` while focused
runtime and providerless acceptance evidence exists and live-provider proof is
still required for Complete.

| ID | Work Item | Implementation Status | Scheduling | Confidence | Required Exit Evidence |
|----|-----------|-----------------------|------------|------------|------------------------|
| EFX-001 | Refuse blind redispatch after an unmatched mutating-tool start; surface the attempt as unconfirmed/`UNKNOWN` | In Progress — runner sandwich + process-death test | Promote — P0 `governance-gap` | High | `tests/test_efx001_interrupted_dispatch.py`; providerless `tests/acceptance/test_efx_durable_effect_flow.py`; live GitHub/browser/provider proof still required for Complete |
| EFX-002 | Inventory effectful tools and fail closed when local policy sees external mutation, regardless of misleading read-only/destructive hints | In Progress — local `external_effect` + fail-closed backends | Promote — P0 `governance-gap` | High | `tests/test_efx002_effect_classification.py`; providerless `tests/acceptance/test_efx_durable_effect_flow.py`; live GitHub/browser/provider proof still required for Complete |
| EFX-003 | Bind one-time approval to run, tool, canonical payload/effect intent, then consume or expire it before dispatch | In Progress — digest-bound consume-once JIT | Promote — P0 `governance-gap` | High | `tests/test_efx003_one_time_approval.py`; providerless `tests/acceptance/test_efx_durable_effect_flow.py`; live GitHub/browser/provider proof still required for Complete |
| EFX-FUTURE | Provider-specific idempotency, settlement, and reconciliation beyond ADR-0042 | Absent | On Hold | Low | Local gaps closed, dated owner promise, provider-enforced identity/status contract, effect-specific fault evidence, and Human Review |

**EFX exit-evidence clarification (2026-09-13 gated-items panel):** the
providerless evidence already proves the guards — EFX-001 crash-consistency
is exercised by a real `os._exit(73)` mid-effect, EFX-002 classification is
static + tested, EFX-003 digest-binding is consume-once tested. The residual
that "live-provider proof" uniquely covers is narrow and falsifiable: **one
real provider mutation observed to behave as classified** (e.g. a GitHub
`create_pr` call passing through the approval/effect path against a real
provider), which requires owner-authorized credentials and target. The gate
holds; the wording is narrowed so it cannot sit unfalsifiably forever.

Evidence and adoption status:
[Durable-Effect Roadmap Socratic Review](analysis/durable-effect-roadmap-socratic-review-2026-08-25.md).
Current execution sequence (non-authoritative):
[Current Roadmap Execution Plan](plans/current-roadmap-execution-plan-2026-08-26.md).

## Roadmap-Neutral Intake - Agentflow v8.2.0 Survey Delta

Survey-derived candidates from the agentflow `b2935f5`→`fcb6878` (v8.2.0)
delta review, 2026-09-13 (record:
`.teaagent/reviews/agentflow-structures-2026-09-12/delta-2026-09-13-v8.2.0.md`,
gitignored). These do not reopen or renumber H0-H6. `Proposed` means documented
and not accepted as implementation-ready; none is scheduled without owner
approval under DR-006. Mechanisms serving existing goals (suggested-default
questions → G1; qualifying-path review rule → EFX-002 conformance) are noted in
the delta record, not listed as rows.

| ID | Work Item | Implementation Status | Scheduling | Confidence | Required Exit Evidence |
|----|-----------|-----------------------|------------|------------|------------------------|
| AGF-001 | Cross-host skill conflict audit: extend `skill explain` (or add `skill audit --inventory`) to enumerate foreign skill roots and Codex/Claude plugin caches read-only, plus a once-per-conflict semantic warning protocol (quote both clauses, name consequence, state which instruction wins) | Complete — `teaagent skill audit` inventories active + foreign roots (`.agents/skills`, plugin caches), marks `loadable`, reports collisions, embeds `SKILL_CONFLICT_PROTOCOL` (`teaagent/skill_loader.py`, `tests/test_skill_audit_inventory.py`) | Complete — implemented 2026-09-13 under owner "implement governance gaps" direction | Medium | Inventory acceptance test over fixture roots; conflict-warning text contract test; no execution of inspected skills |
| AGF-002 | Inline incident citations on the two uncited guards (`check_dr006_gate_trailer`, `check_action_register_link`), matching the cite-originating-failure convention of peer guards | Complete — both guards carry `Origin:` paragraphs citing the 2026-09-09 review failure (landed `86fa25ea`) | Complete — verified 2026-09-13 | High | Guard comments cite originating failure; no behavior change |
| AGF-003 | Run-store retention/prune policy for completed inactive records (agentflow `completion-cleanup` analog: opt-in, Trash-equivalent, age-gated) | Absent — no retention in `run_store.py`/`run_logging.py` | On Hold — premature at zero organic delivery traffic; re-propose when organic runs exist | Low | Retention policy spec + prune acceptance test over fixture run store |
| AGF-004 | `metadata.version` (or equivalent) field in SKILL.md frontmatter as single per-skill version source | Absent — frontmatter is `name`/`description` only | On Hold — no consumer asks for per-skill versions; revisit if marketplace ships independently versioned skills | Low | Version field parsed + surfaced in `skill explain` |

## Roadmap-Neutral Intake - Vendor Direction Survey 2026-09-13

Survey of OpenAI / Anthropic / Google DeepMind agent-and-governance
directions (record:
`.teaagent/reviews/vendor-directions-2026-09-13/survey-record.md`,
gitignored). Conclusion: all three vendors now treat the **harness/environment
layer** as the security boundary — validating harness-first. Rows below are
the only gaps the survey surfaced; none is scheduled without owner approval
under DR-006.

| ID | Work Item | Implementation Status | Scheduling | Confidence | Required Exit Evidence |
|----|-----------|-----------------------|------------|------------|------------------------|
| VND-001 | Live supervisor/monitor lane: trusted reviewer pass over the run trajectory (post-run first, in-run later) classifying events against a threat taxonomy; acceptance shaped on DeepMind's coverage/recall/time-to-response metrics | Implemented — `teaagent/run_review.py` post-run reviewer classifies each tool call against the insider-threat taxonomy via `teaagent runs review <run_id>`; in-run live monitor remains future | Complete — implemented 2026-09-14 under owner authorization + `governance-gap` DR-006 gate | Medium | Post-run reviewer pass over fixture audit log; taxonomy-classified findings; coverage metric reported (`tests/test_run_review.py`, 7 tests) |
| VND-002 | Insider-threat/misalignment threat class in `docs/threat-model.md` — agents as potential insider threats (DeepMind AI Control framing), not only external attackers | Complete — insider-threat class added to `docs/threat-model.md` (new threat-table row + dedicated section) | Complete — implemented 2026-09-14 under owner "implement tasks" direction | High | Threat-model section added; no behavior change |
| VND-003 | Agent-autonomy metrics (check-in rate, interruption rate, pause-vs-assume calibration — Anthropic's measuring-agent-autonomy shape) | Absent — same zero-organic blocker as G1 | On Hold — no organic runs to measure; re-propose when M4 dogfood lands | Low | Metric definitions + instrumented run fields |

## Milestones

| Milestone | Target | Outcome | Owner | Status | Confidence | Next Gate | Exit Criteria |
|-----------|--------|---------|-------|--------|------------|-----------|---------------|
| M0 | 1-2 weeks | Risk register operational, release claims traceable, tool lint warnings budgeted | governance | Complete | High | M1 complete | All 3 checks pass: `validate_docs_consistency.py`, `refresh_competitive_docs.py --check`, `teaagent tool lint --root .` |
| M1 | 2-6 weeks | Daily cockpit parity, run evidence summary, guided recovery | TBD | Complete | High | M2 complete | CLI/TUI cockpit parity acceptance, run evidence summary acceptance, guided recovery acceptance |
| M2 | 4-10 weeks | Long-session context health, hash-bound plans, scope creep measurement | TBD | Complete | High | M3 complete | Long-session context guard acceptance, scope budget acceptance, plan revision acceptance |
| M3 | 8-14 weeks | Extension activation explain, MCP trust onboarding, subagent review/merge | TBD | Complete | High | M4 complete | Extension activation explain acceptance, MCP trust onboarding acceptance, subagent review/merge acceptance |
| M4 | 12-22 weeks | Background/cloud durability, gateway task intake, control-plane operator cockpit | TBD | On Hold except DR-006 dogfood carve-out | Low | Dated BG-001/cockpit dogfood evidence | Only background lifecycle + operator cockpit are eligible under co-maintainer dogfood; cloud/SaaS/multi-tenant GTM remains held. Eligibility is not need or completion |
| M5 | Ongoing | Prompt/runtime/model/provider gating, repo-map benchmarking, release evidence bundles | TBD | Blocked — fixture corpus gated | Low | Funded non-advisory release profile + owner decision | Prompt/conversational regression suite and repo-map fixture corpus are in the release profile; model/provider regression evidence remains external |
| M6 | After M1-M4 | Desktop/client-server packaging for owner-operated trust, update, rollback, session attach | TBD | On Hold — no authorized owner demand | Low | Owner friction or dated override | Packaged launch smoke, signing/SBOM/update docs, and desktop session-attach acceptance remain future contracts |

## Track A - Roadmap Governance and Claim Hygiene

| ID | Work Item | Owner | Status | Confidence | Next Gate | Risk |
|----|-----------|-------|--------|------------|-----------|------|
| GOV-001 | Create canonical roadmap status table | TBD | Complete | High | GOV-002 | Medium |
| GOV-002 | Add risk-register schema | docs / governance | Complete | High | release audit | High |
| GOV-003 | Add claim-to-evidence matrix | docs / governance | Complete | High | release audit | High |
| GOV-004 | Define verification profiles | docs / governance | Complete | High | release audit | High |
| GOV-005 | Add warning-budget ownership | docs / governance | Complete | High | release audit | Medium |
| GOV-006 | Create release-channel source of truth | docs / governance | Complete | High | release audit | Medium |
| GOV-007 | Make competitive survey freshness a release checklist blocker | docs / governance | Complete | High | release audit | Medium |
| GOV-008 | Add decision expiry dates to ADRs | docs / governance | Complete | High | ADR review | Medium |
| GOV-009 | Add issue template for roadmap tasks | docs / governance | Complete | High | backlog refinement | Low |
| GOV-010 | Tag backlog items by user journey | docs / governance | Complete | High | backlog refinement | Low |
| GOV-011 | Create "do not claim" list | docs / governance | Complete | High | release audit | Medium |
| GOV-012 | Add release residual-risk summary | docs / governance | Complete | High | release audit | High |
| GOV-013 | Create curated documentation front door | docs | Complete | High | GOV-014 | Low |
| GOV-014 | Add doc-vs-HEAD guarded claim registry | docs / verification | Complete | High | release audit | High |
| GOV-015 | Audit High/Critical module risks for upward links | docs / module owners | Complete | High | GOV-016 | High |

## Track H3 - Ecosystem Trust And Dynamic Skills

The June 5 dynamic-skill research narrows the first H3 proof point: TeaAgent
should not expand ecosystem breadth until generated skills, long results, and
skill-output verification are testable against the RSS failure case.
DSK-P0-001 through DSK-P0-007 (lifecycle state machine, write quarantine,
offline RSS fixture, long-result envelope, output validators, explainability,
and decision-visibility) form the first ecosystem-trust spine.

| ID | Work Item | Owner | Status | Confidence | Next Gate | Risk |
|----|-----------|-------|--------|------------|-----------|------|
| DSK-P0-001 | Skill lifecycle state machine distinguishes loaded, activated, used, and verified. | skills / audit | Complete | High | lifecycle event tests | High |
| DSK-P0-002 | Direct active-skill writes are blocked, quarantined, or labeled unmanaged. | workspace tools / skill writer | Complete | High | protected path acceptance | High |
| DSK-P0-003 | Offline RSS fixture acceptance proves source-backed skill output. | tests / skills | Complete | High | fixture summary test | High |
| DSK-P0-004 | Long-result envelope preserves preview, full artifact, hash, and cursor. | tools / audit | Complete | High | large result fixture test | High |
| DSK-P0-005 | Output artifact validators for source-backed tasks. | tests / verifier | Complete | High | validator test suite | High |
| DSK-P0-006 | Unmanaged skill explainability state labels candidate, shadowed, and blocked skills. | skill loader / CLI | Complete | High | explainability state test | High |
| DSK-P0-007 | Invalid tool-decision failure is visible in skill flows, not silently successful. | chat agent / runner | Complete | High | invalid-decision test | High |
| DSK-P1-001 | Behavioral skill eval compares with-skill and without-skill results. | skill eval | Complete | High | deterministic eval harness | Medium |
| DSK-P1-002 | Skill invocation audit records activation cause and output artifact links. | audit / run store | Complete | High | run evidence integration | Medium |
| DSK-P1-003 | Explicit skill activation UX is available through CLI/task config first. | CLI / runner | Complete | High | explicit activation acceptance | Medium |

Current evidence package:

- [Dynamic Skill Generation And Long Result Audit](analysis/dynamic-skill-generation-and-long-result-audit-2026-06-05.md)
- [RSS Dynamic Skill Failure Case Study](analysis/rss-failure-case-study-2026-06-05.md)
- [Agent Ecosystem Core Values](strategy/agent-ecosystem-core-values-2026-06-05.md)
- [Dynamic Skill Critical Questioning](reviews/dynamic-skill-critical-questioning-2026-06-05.md)
- [Dynamic Skill And Long Result Work Items](plans/dynamic-skill-and-long-result-work-items-2026-06-05.md)
- [Dynamic Skill Lifecycle And Result Flow](architecture/dynamic-skill-lifecycle-and-result-flow-2026-06-05.md)

## Cross-Horizon Track - Seven Control Loops

The June 5 competitor pass identifies seven control loops that should become
TeaAgent's architecture and product governance model across H0-H5:
spec-first direction, dynamic workflow breadth, loop/goal depth, model routing,
synthesis review, precise memory, and human review gates. This track is
cross-horizon because each loop touches multiple existing modules rather than a
single roadmap horizon.

`Complete` below records the implementation state of the listed historical
items. It does not authorize follow-on work. This survey-derived
`legacy-competitive` track remains held unless a new item cites owner friction,
an independently proved governance gap, or a dated owner override.

| ID | Work Item | Owner | Status | Confidence | Next Gate | Risk |
|----|-----------|-------|--------|------------|-----------|------|
| SCL-P0-001 | Bind high-risk runs to a spec or plan receipt. | plan gate / runner | Complete | High | failing high-risk no-spec test | High |
| SCL-P0-002 | Add repo-grounding checks before spec tasks execute. | plan gate / code map | Complete | High | stale-spec fixture test | High |
| SCL-P0-003 | Link dynamic skill lifecycle and long-result work as the H3 proof path. | skills / docs | Complete | High | DSK-P0 link audit | High |
| SCL-P0-004 | Define persisted goal records for loop state, evidence, and stop criteria. | runner / run store | Complete | High | goal record schema test | High |
| SCL-P0-005 | Add model-route receipts to audit and run evidence. | model routing / audit | Complete | High | deterministic route fixture | Medium |
| SCL-P0-006 | Define synthesis review artifacts for high-risk answers. | review / evidence | Complete | High | contradictory-source fixture | High |
| SCL-P0-007 | Define human review gate packets for irreversible actions. | approval / TUI | Complete | High | destructive action packet test | High |
| SCL-P1-001 | Add typed memory metadata: scope, source, confidence, TTL, supersession, owner. | memory | Complete | High | memory promotion tests | High |
| SCL-P1-002 | Add memory quarantine and promotion flow. | memory / review | Complete | High | unreviewed memory injection test | High |
| SCL-P1-003 | Add goal status and evidence inspection commands. | CLI / TUI | Complete | High | status command acceptance | Medium |
| SCL-P1-004 | Add role-aware model routing tests. | model routing | Complete | High | route matrix tests | Medium |
| SCL-P1-005 | Require synthesis review for source-backed high-risk research. | review / docs | Complete | High | review requirement validator | Medium |
| SCL-P1-006 | Add gate packets to skill install and memory promotion. | skills / memory / approval | Complete | High | gate packet acceptance | High |
| SCL-P2-001 | Build a TUI cockpit for spec, goal, route, review, memory, and approval state. | TUI | Complete | High | cockpit prototype | Medium |
| SCL-P2-002 | Add release evidence bundle for all seven loops. | release / docs | Complete | High | release bundle check | Medium |

Current evidence package:

- [Seven Control Loops Competitor Survey](analysis/seven-control-loops-competitor-survey-2026-06-05.md)
- [Seven Control Loops Product Direction](strategy/seven-control-loops-product-direction-2026-06-05.md)
- [Seven Control Loops TeaAgent Integration Map](architecture/seven-control-loops-teaagent-integration-map-2026-06-05.md)
- [Seven Control Loops Critical Questioning](reviews/seven-control-loops-critical-questioning-2026-06-05.md)
- [Seven Control Loops Work Items](plans/seven-control-loops-work-items-2026-06-05.md)

## Cross-Horizon Track - Community Pain Point Overlay

The June 5 community pass adds a user-pain overlay to the seven control loops.
The work is deliberately receipt-oriented: make routing, memory, review, cost,
skill/MCP, approval, goal, and proof-of-use behavior visible before widening
autonomy.

`Complete` below records implementation that already landed; it is not evidence
of current community demand. Follow-on community-survey work is held unless it
passes the same DR-006 authority gate as any other hypothesis-derived item.

| ID | Work Item | Owner | Status | Confidence | Next Gate | Risk |
|----|-----------|-------|--------|------------|-----------|------|
| CPP-P0-001 | Add route evidence panel to run summary. | model routing / run evidence | Complete | High | model route fixture | High |
| CPP-P0-002 | Add goal checkpoint receipt. | runner / run store | Complete | High | long-goal checkpoint test | High |
| CPP-P0-003 | Add memory write quarantine rule for agent-created project memory. | memory / approval | Complete | High | pending-memory test | High |
| CPP-P0-004 | Add review artifact minimum schema. | review / subagents | Complete | High | missing-evidence review test | High |
| CPP-P0-005 | Add approval authority receipt. | approval / audit | Complete | High | exact-scope authority test | High |
| CPP-P0-006 | Add dynamic asset provenance summary. | skills / MCP / audit | Complete | High | dynamic asset evidence test | High |
| CPP-P0-007 | Add proof-of-use requirement for skill-backed outputs. | skills / runner | Complete | High | skill-backed output test | High |
| CPP-P0-008 | Add intent-drift pre-write check for high-risk runs. | plan gate / policy | Complete | High | out-of-scope write test | High |
| CPP-P1-001 | Add review repeat suppression. | review / evidence | Complete | High | repeated finding state test | Medium |
| CPP-P1-002 | Add phase budget thresholds. | budget / model routing | Complete | High | phase budget test | Medium |
| CPP-P1-003 | Add context pressure score. | context bus / TUI | Complete | High | context score test | Medium |
| CPP-P1-004 | Add untrusted-source memory tests. | tests / memory | Complete | High | memory poisoning fixture | High |
| CPP-P1-005 | Add risk-adaptive spec exemption UX. | plan gate / CLI | Complete | High | low-risk exemption test | Medium |
| CPP-P2-001 | Add control-plane cockpit. | TUI | Complete | High | cockpit acceptance test | Medium |

Current evidence package:

- [Community Agent Pain Points Survey](analysis/community-agent-pain-points-survey-2026-06-05.md)
- [Community Pain Points Response Plan](plans/community-pain-points-response-plan-2026-06-05.md)

## Status Definitions

- **Proposed**: Item is documented and not yet accepted as implementation-ready
- **Complete**: Item is fully implemented and verified
- **In Progress**: Item is actively being worked on
- **Pending**: Item is not yet started
- **Blocked**: Item is blocked by dependencies
- **On Hold**: Item is intentionally deferred

## Confidence Definitions

- **High**: High confidence in approach and timeline
- **Medium**: Moderate confidence, some unknowns remain
- **Low**: Low confidence, significant unknowns or dependencies

## Critical Path — Current Completion Evidence

| Item | Status | Completion % | Evidence Type | Owner | Notes |
|------|--------|:---:|---|---|---|
| SEC-01 Audit HMAC persistence | **Fixed** | 100% | Code + passing tests | — | Key persisted at `teaagent/audit.py:163`; RISK-01 hardening: key-save OSError now logs warning (no silent pass); `HMACKeySaveTests::test_chain_key_save_failure_logs_warning` |
| SEC-17 ApprovalPolicy thread leak | **Fixed** | 100% | Code + passing tests | — | ENG-01: `__del__` shuts down executor; `ApprovalPolicyThreadLeakTests` |
| SEC-18 Zero cost rates (fake/ollama/vllm) | **Fixed** | 100% | Code + passing tests | — | RISK-02: nominal non-zero rates; `ProviderCostRateTests` |
| SEC-19 JIT approval no timeout | **Fixed** | 100% | Code + passing tests | — | OPS-01: 60s default timeout, auto-deny; `JITApprovalTimeoutTests` |
| SEC-02 MCP trust expiry | **Fixed** | 100% | Code + passing test | — | `teaagent/mcp_trust.py:286`, `teaagent/mcp_trust.py:343`; `test_server_trust_expiry()` |
| SEC-04 Budget default | **Fixed** | 100% | Code + passing tests | — | Default 500 cents; `test_budget_zero_cents_rejects_any_spend()` |
| SEC-06 JIT isolation | **Fixed** | 100% | Code + passing tests | — | `test_subagent_jit_approval_isolation_sec06()` |
| SEC-07 Docker hardening | **Fixed** | 100% | Code + passing tests | — | `teaagent/subagents/_isolation.py:347-365`; `test_docker_isolation_*()` |
| SEC-10 Shell allowlist | **Fixed** | 100% | Code + passing tests | — | `teaagent/workspace_tools/_shell.py:174`; `test_all_inspect_commands_classified_as_inspect()` |
| DS-02 TUI controller routing | **Fixed** | 100% | Code + passing tests | — | `teaagent/tui/core.py:996`; controller-based cost/undo/task |
| DS-05 TUI undo via journal | **Fixed** | 100% | Code + passing tests | — | `teaagent/tui/core.py:1057`; `test_tui_undo_uses_journal()` |
| DS-09 Background UUID rejection | **Fixed** | 100% | Code + passing test | — | `test_agent_run_background_rejects_known_run_or_suspension_id()` |
| DS-12 Empty-path approval | **Fixed** | 100% | Code + passing tests | — | `test_empty_path_globs_rejected_ds12()` |
| DS-13 Budget zero semantics | **Fixed** | 100% | Code + passing tests | — | `None`=unlimited, `0`=no-spend |
| DS-01 TUI cost accumulation | **Fixed** | 100% | Code + passing tests | — | TICKET-12; `test_task003_cost_truth.py` |
| DS-08 resume always errors | **Fixed** | 100% | Code + passing tests | — | TICKET-16 Phase 2; `test_repl_suspend_resume_roundtrip` |
| DS-11 Initial task dropped | **Fixed** | 100% | Code + passing tests | — | TASK-DD2-001; chat task forwarding tests |
| H0 Claim + risk hygiene | Complete | 100% | Code + docs | governance | All H0 items done; risk register has Owner/Due; M0 checks pass |
| M0 Risk register operational | Complete | 100% | Code + docs | governance | All 3 M0 checks verified passing |

**Merge gate:** `python3 scripts/validate_docs_consistency.py` must pass before any PR that updates roadmap or risk register status.

**Unverified ecosystem claims:** See `docs/security/risk-register-and-threat-model-2026-06-02.md` Appendix C for a full list of aspirational claims that must not be marked as shipped without test evidence.

## Notes

- This document should be updated when roadmap items change status
- Every roadmap item should have exactly one owner surface
- Status changes should be traceable via git history
- This document is referenced by release checklist and docs validators
- Documentation-current-truth work is tracked in
  `docs/plans/documentation-optimization-master-plan-2026-06-04.md` and
  `docs/work-log/documentation-optimization-work-items-2026-06-04.md`
- Phase 0 governance closure evidence is tracked in
  `docs/work-log/phase-0-governance-closure-report-2026-06-04.md`
- Full pytest collection is expected to run from the development environment
  declared in `pyproject.toml`; `hypothesis` already appears under
  `project.optional-dependencies.dev`, so the June 11 collection failure was an
  environment provisioning gap rather than a missing dependency declaration.
