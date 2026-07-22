# Consensus Validation Disposition Spec (ADR-0029 Expiry Package)

> **Claim class:** Forward-looking specification (planned/held work — NOT current truth).
>
> **Status:** Preparation artifact for held item.
>
> **Date:** 2026-07-11
>
> **Trigger:** Owner request 2026-07-11 — forward-spec held/external roadmap items
> so future execution has pinned contracts and executable holds.
>
> **Scheduling gate (DR-006):** ADR-0029 expiry review **2026-12-10**
> (`docs/adr/0029-consensus-validation-deferred.md`): choose **wire behind
> approval queue** or **delete/quarantine** with import-graph evidence.
>
> **Owns:** The decision package for that expiry review — both options fully
> specified, plus the behavioral baseline the decision relies on.
>
> **Does not own:** Current-truth status (`docs/roadmap-status.md`), the
> deferral decision itself, ADR statuses.
>
> **Review trigger:** ADR-0029 expiry (2026-12-10), or owner demand for a
> multi-agent consensus gate before then.

## 1. Current verified state (2026-07-11, HEAD)

- Module: `teaagent/consensus/consensus_validation.py` (658 lines) —
  `ConsensusRuleType` (`:37-44`, N_OF_M / UNANIMOUS / MAJORITY /
  SUPERMAJORITY / ROLE_BASED), `ConsensusRule.check_consensus`
  (`:61-134`, with optional `voter_roles` mapping added 2026-06-30, commit
  `b633ca6`), `ConsensusRequest` (`:167-248`), `ConsensusStore`
  (tenant-scoped JSON under `.teaagent/`, `:251-434`), `ConsensusValidator`
  (`request_consensus`/`cast_vote`/`get_consensus_status`, `:437-657`).
- **Docs drift (recorded finding):** ADR-0029 cites
  `teaagent/consensus_validation.py`. The module physically moved to
  `teaagent/consensus/consensus_validation.py`; the old dotted path still
  imports only via the deprecation shim
  (`teaagent/_compat_modules.py:22`). `tests/test_consensus.py:6` still uses
  the deprecated path (exercising the shim); `tests/test_import_compat_wdf002.py`
  covers both paths deliberately.
- **Unwired, verified:** no production module under `teaagent/` imports
  `consensus_validation`. `teaagent/consensus/__init__.py` does **not**
  re-export it. The CLI `consensus *` commands import the **ADR-0019
  federated engine** (`teaagent/cli/_handlers/_consensus.py:10-26` →
  `teaagent.consensus` `ConsensusEngine`) — a different system.
- Watch-list: `scripts/validate_wiring.py:32` names the module, satisfying
  ADR-0029 clause 3.
- The three consensus surfaces (per ADR-0029 context):
  | Surface | Location | Status |
  | --- | --- | --- |
  | Federated swarm consensus (ADR-0019) | `teaagent/consensus/` engine | Wired: CLI `consensus *` commands |
  | Centralized subagent approval queue (ADR-0022) | `teaagent/subagents/` queue stores | Wired: production approval path |
  | `consensus_validation` (this module) | `teaagent/consensus/consensus_validation.py` | **Experimental — unwired** (ADR-0029) |

## 2. The hold and its gate

ADR-0029 (Accepted 2026-06-10) defers wiring until **2026-12-10** to avoid a
third parallel consensus surface. Destructive actions flow through the
approval queue + JIT approval coordinator only. Nothing here changes that;
this spec exists so the expiry review is a decision, not an investigation.

### 2.1 Pre-deletion preservation record (2026-07-22)

This section exists so `consensus_validation` remains recoverable after Option D
deletes the code. Deletion must remove the runtime surface, not the historical
intent, feature inventory, or revival path.

#### 2.1.1 Original intent

`consensus_validation` was intended as a **post-approval multi-agent consensus
validator** for collaborative or destructive actions that had already passed the
normal approval queue. It was never supposed to replace ADR-0022's centralized
approval queue; the safe wiring shape was a second key behind the queue for a
narrow action class.

The surviving design question, if revived, is: "Do we need a separate N-of-M /
role-based sign-off gate after the existing queue has approved a destructive
action?" Absent that owner friction or governance-gap evidence, DR-006 favors
deletion over preserving dormant code.

#### 2.1.2 Feature inventory to preserve in history

The module at `teaagent/consensus/consensus_validation.py` contained:

| Area | Symbols / behavior | Revival note |
| --- | --- | --- |
| Status model | `ConsensusStatus`: `pending`, `approved`, `rejected`, `expired`, `cancelled` | Keep terminal-state semantics explicit if rebuilt. |
| Rule model | `ConsensusRuleType`: `N_OF_M`, `UNANIMOUS`, `MAJORITY`, `SUPERMAJORITY`, `ROLE_BASED`; `ConsensusRule.check_consensus()` | Rebuild only the rule types needed by real policy; do not automatically restore `SUPERMAJORITY`. |
| Role-based voting | `ROLE_BASED` rules consult `voter_roles`; absent a mapping, `voter_id` is treated as the role | This was the 2026-06-30 A-P2-7 fix; keep it if role-based consensus returns. |
| Request model | `ConsensusRequest`: action, context, requester, votes, voter roles, timestamps, expiry, metadata | Revote currently overwrote silently; audited revote events are required before destructive-action wiring. |
| Storage | `ConsensusStore`: tenant-scoped JSON under `.teaagent/consensus-rules` and `.teaagent/consensus-requests` using `atomic_write_text` | Reuse only if file-backed request state is still desired; otherwise prefer the approval queue's store. |
| Validator facade | `ConsensusValidator`: `create_rule`, `request_consensus`, `cast_vote`, `get_consensus_status`, `create_default_rules` | Facade was not imported by production paths. A revived version must integrate through the approval queue. |
| Policy bridge | `create_rule()` created `PolicyType.CONSENSUS` allow policies with `rule_id` metadata | Bridge was inert without a queue hook; rebuild with a real policy condition contract or delete it. |
| Default rules | 2-of-3 production deploy, unanimous destructive action, majority operational decision | Treat as examples, not product requirements. |

Known wire-blockers that history must not hide:

- `SUPERMAJORITY` counted only votes cast, not `total_voters`; a single YES vote
  could approve. Destructive-action revival must use quorum semantics or remove
  this rule type from wireable policy.
- `ConsensusRequest.add_vote()` overwrote prior votes silently. Revival needs an
  audited revote or immutable-vote contract.
- The module emitted no ADR-0032 audit events and had no approval-queue hold
  hook. Any revival starts with the event/queue integration, not the old facade.
- The CLI `consensus *` commands used the separate ADR-0019 federated engine;
  they were not proof that this validation module was live.

#### 2.1.3 Git recovery path

Known-good code anchor when this preservation record was written:
`7a7799d` (`docs: record owner-ratified intent decisions and intent-roadmap survey`).
The deletion commit's parent should also contain the final pre-deletion code.

To find the deleted module later:

```bash
git log --all --follow -- teaagent/consensus/consensus_validation.py
git show 7a7799d:teaagent/consensus/consensus_validation.py
git show <deletion_commit>^:teaagent/consensus/consensus_validation.py
```

To restore the last pre-deletion implementation for investigation, not automatic
re-adoption:

```bash
git restore --source=<deletion_commit>^ -- teaagent/consensus/consensus_validation.py
git restore --source=<deletion_commit>^ -- tests/test_consensus.py tests/test_consensus_disposition_spec.py
```

Then re-run the decision matrix in §3.3. Restoring from history is evidence
recovery, not authority to wire the module.

## 3. Future contract — both options

### 3.1 Option W: wire behind the approval queue

Position: **post-queue validation** for destructive actions that already
passed individual approval and are flagged (by policy) as requiring N-of-M /
role-based sign-off. It must never replace the queue (that was the ADR-0029
worry); it adds a second key for a narrow action class.

- Integration point: where the approval queue finalizes an approval decision
  for a destructive call (the ADR-0022 queue resolution path in
  `teaagent/subagents/` — exact hook chosen at wiring time; candidate: the
  coordinator that flips a queued approval to granted). On approval-granted
  for an action matching a consensus policy, create
  `request_consensus(rule_id, action, context, requested_by)` and hold the
  call in `pending_approval` until the request resolves.
- Event contract: audit events `consensus_requested`,
  `consensus_vote_cast`, `consensus_{approved|rejected|expired}` with
  `{request_id, rule_id, action, voter_id?, status}` — folded onto the
  ADR-0032 spine as consumer-visible audit events (no new interceptor class
  needed; the queue hold already blocks execution).
- Config surface: consensus rules bound to policy conditions (reuse
  `PolicyType` machinery rather than a parallel matcher).
- **Wire-blockers found by the behavioral baseline (must fix before wiring):**
  1. **SUPERMAJORITY quorum bug-by-design:** `check_consensus` computes the
     2/3 threshold over votes *cast*, not `total_voters`
     (`consensus_validation.py:109-115`). A single YES vote approves
     (1 ≥ 2/3·1). For a destructive-action gate this is unacceptable; wiring
     requires quorum semantics (threshold over `total_voters`) or removal of
     SUPERMAJORITY from wireable rule types.
     Pinned by `test_supermajority_threshold_is_over_cast_votes_not_total`.
  2. Vote mutation: `add_vote` overwrites a voter's prior vote silently
     (`:183-195` dict assignment). Acceptable for advisory use; for a
     destructive gate, revote must be an audited event.
- Rollback: unwire = remove the single queue-side hook; storage is inert JSON.

### 3.2 Option D: delete/quarantine

Justified when, at expiry: no owner demand signal (DR-006 T1), zero
production imports (the import-graph guard test provides continuous
evidence), and the approval queue has handled all real multi-agent
coordination needs.

Deletion checklist:
1. Delete `teaagent/consensus/consensus_validation.py`; remove the shim row
   `teaagent/_compat_modules.py:22`; remove watch-list row
   `scripts/validate_wiring.py:32`.
2. Retire tests: `tests/test_consensus.py`, the consensus rows of
   `tests/test_import_compat_wdf002.py`, the voter-roles cases in
   `tests/test_inline_todo_resolutions.py`, and
   `tests/test_consensus_disposition_spec.py` (this spec's companion) — in
   the **same commit**, with the traceability matrix updated (harness-first
   §4.2 deletion policy).
3. Update ADR-0029 (Accepted → Superseded/Closed with the decision), the
   roadmap-verification held-table row, and `docs/plans/ticket-plans/inline-todos.md`
   if the module carries catalog entries.
4. Run `scripts/validate_wiring.py` and `scripts/validate_docs_consistency.py`.

### 3.3 Decision matrix (prepared for the owner)

| Criterion | Favors W | Favors D |
| --- | --- | --- |
| Owner friction entry citing multi-agent sign-off need | required | absent |
| Co-maintainer dogfood shows queue insufficiency (two agents editing one surface) | yes | no such incident by expiry |
| Willingness to fix the SUPERMAJORITY quorum semantics | yes | no |
| Appetite for a third consensus surface's maintenance | accepted | rejected (default posture per ADR-0029) |

Default recommendation absent new evidence: **Option D** — the module has
had zero production demand since 2026-06-10, and ADR-0029's own rationale
(avoid parallel consensus systems) still holds.

## 4. Executable specification

Tests live in `tests/test_consensus_disposition_spec.py`.

| Contract clause | Test | Kind |
| --- | --- | --- |
| No production import of consensus_validation (ADR-0029 clause 1) | `test_consensus_validation_has_no_production_imports` | guards hold today — failure = someone wired it; that must be the deliberate §3.1 decision |
| Wiring-validator watch-list names the module (clause 3) | `test_wiring_validator_watchlist_names_module` | guards hold today |
| N_OF_M rejects exactly when approval is impossible | `test_n_of_m_rejects_only_when_approval_impossible` | baseline for §3.1 |
| SUPERMAJORITY threshold is over cast votes (quirk pin) | `test_supermajority_threshold_is_over_cast_votes_not_total` | baseline — wire-blocker evidence |
| Revote silently overwrites (quirk pin) | `test_add_vote_overwrites_prior_vote_silently` | baseline — wire-blocker evidence |
| cast_vote refuses unknown/terminal requests; expiry flips status | `test_cast_vote_lifecycle_guards` | baseline for §3.1 event contract |

Existing coverage (not duplicated): rule-type outcomes, store round-trips,
tenant isolation (`tests/test_consensus.py`); ROLE_BASED voter_roles
semantics (`tests/test_inline_todo_resolutions.py`).

## 5. Expiry-day checklist (2026-12-10)

1. Read the guard test history: has
   `test_consensus_validation_has_no_production_imports` ever been touched?
   (Any change = investigate wiring attempts.)
2. Check friction log for multi-agent sign-off entries; apply §3.3 matrix.
3. Execute §3.1 (with wire-blocker fixes) or §3.2 wholesale — no partial
   states; a half-wired consensus gate is worse than either option.
4. Update ADR-0029 status and this spec's status line in the same commit.

## 6. Risks and open questions

- **Three-surface confusion is already real:** the CLI `consensus` commands
  operate the ADR-0019 engine while this module shares the package name.
  Any future doc citing "consensus" must name the ADR. (This spec does.)
- **Silent bit-rot:** unwired code drifts. The behavioral baseline tests
  double as a canary — if the module stops passing them, delete leans harder.
- Open: if Option W is chosen, do consensus votes come from human owners
  only, or may co-maintainer agents vote? Owner call; default: humans only
  (agents request, never approve — consistent with the approval-queue
  posture).
