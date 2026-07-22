# Consensus Validation Disposition Spec (ADR-0029 Expiry Package)

> **Claim class:** Executed deletion / historical recovery record.
>
> **Status:** ADR-0029 Option D executed 2026-07-22; runtime surface deleted,
> intent and recovery path preserved.
>
> **Date:** 2026-07-11; executed 2026-07-22.
>
> **Trigger:** Owner request 2026-07-11 prepared the expiry package; owner
> direction-review 2026-07-22 chose delete/quarantine.
>
> **Scheduling gate (DR-006):** resolved by ADR-0029 Option D.
>
> **Owns:** The historical design inventory, wire-blockers, deletion checklist,
> and git recovery path for the deleted `consensus_validation` module.
>
> **Does not own:** Current live consensus behavior (ADR-0019 engine), the
> centralized approval queue (ADR-0022), or authority to revive/wire the deleted
> module.
>
> **Review trigger:** Owner demand for a post-approval multi-agent consensus
> gate; otherwise this record is archival.

## 1. Historical pre-deletion state (2026-07-11 to 2026-07-22)

- Module before deletion: `teaagent/consensus/consensus_validation.py` (658
  lines) — `ConsensusRuleType` (N_OF_M / UNANIMOUS / MAJORITY / SUPERMAJORITY /
  ROLE_BASED), `ConsensusRule.check_consensus` (with optional `voter_roles`
  mapping added 2026-06-30, commit `b633ca6`), `ConsensusRequest`,
  `ConsensusStore`, and `ConsensusValidator` (`request_consensus` / `cast_vote`
  / `get_consensus_status`).
- **Pre-deletion import state:** no production module under `teaagent/` imported
  `consensus_validation`; the only compatibility path was the deprecated alias
  `teaagent.consensus_validation` in `teaagent/_compat_modules.py`.
- **Deleted in ADR-0029 Option D:** the module, the deprecated alias, the wiring
  watch-list row, `tests/test_consensus.py`, `tests/test_consensus_disposition_spec.py`,
  consensus-validation rows in `tests/test_import_compat_wdf002.py`, and the
  voter-role cases in `tests/test_inline_todo_resolutions.py`.
- The two remaining consensus surfaces are:
  | Surface | Location | Status |
  | --- | --- | --- |
  | Federated swarm consensus (ADR-0019) | `teaagent/consensus/` engine | Wired: CLI `consensus *` commands |
  | Centralized subagent approval queue (ADR-0022) | `teaagent/subagents/` queue stores | Wired: production approval path |

The removed `consensus_validation` design is preserved below for git-history
recovery only; restoring it is not authority to wire it.

## 2. The closed hold and its gate

ADR-0029 (Accepted 2026-06-10) deferred wiring to avoid a third parallel
consensus surface. Owner decision on 2026-07-22 chose Option D. Destructive
actions still flow through the approval queue + JIT approval coordinator only.
This spec now exists as the recovery record for the deleted validation design.

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

### 3.2 Option D: delete/quarantine — executed 2026-07-22

Justified by: no owner friction entry requiring an extra consensus gate, zero
production imports, and the existing approval queue covering real destructive
action governance.

Deletion checklist result:
1. Deleted `teaagent/consensus/consensus_validation.py`; removed the shim row in
   `teaagent/_compat_modules.py`; removed the watch-list row in
   `scripts/validate_wiring.py`.
2. Retired tests: `tests/test_consensus.py`, consensus-validation rows of
   `tests/test_import_compat_wdf002.py`, voter-role cases in
   `tests/test_inline_todo_resolutions.py`, and
   `tests/test_consensus_disposition_spec.py`.
3. Updated ADR-0029, this spec, roadmap/backlog/reference docs, and
   `docs/plans/ticket-plans/inline-todos.md`.
4. Required verification: `scripts/validate_wiring.py`,
   `scripts/validate_docs_consistency.py`, focused tests, and a reference scan
   for stale production imports.

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

## 4. Executable specification after deletion

The old executable spec `tests/test_consensus_disposition_spec.py` was retired
with the runtime module it pinned. The active guard is now
`tests/test_docs_consistency.py::test_consensus_validation_deletion_preserves_recovery_record`.

| Contract clause | Test | Kind |
| --- | --- | --- |
| Deletion preserves original intent, feature inventory, wire-blockers, and git recovery commands | `test_consensus_validation_deletion_preserves_recovery_record` | guards archaeology after runtime deletion |

Existing live consensus coverage remains with ADR-0019 tests (`tests/test_consensus_cli.py`,
`tests/test_consensus_engine_history.py`, and `tests/acceptance/test_consensus_flow.py`);
those tests are unrelated to the deleted validation module.

## 5. Revival checklist

1. Recover the deleted module from git history using §2.1.3.
2. Re-run the decision matrix in §3.3 against current owner friction and
   governance-gap evidence.
3. If Option W is chosen in the future, rebuild the module behind the approval
   queue, fix the SUPERMAJORITY quorum semantics, add audited revote events,
   and add ADR-0032 audit events before any destructive-action wiring.
4. Update ADR-0029 with the new owner decision in the same commit.

## 6. Risks and open questions

- **Two-surface clarity is now required:** the CLI `consensus` commands operate
  the ADR-0019 engine. Future docs must not imply the deleted
  `consensus_validation` module is live; references to it are historical or
  recovery-only.
- **History recovery risk:** restoring deleted code from git can revive stale
  semantics. Treat recovery as evidence collection until a new owner/governance
  decision authorizes a rebuild.
- Open: if Option W is chosen, do consensus votes come from human owners
  only, or may co-maintainer agents vote? Owner call; default: humans only
  (agents request, never approve — consistent with the approval-queue
  posture).
