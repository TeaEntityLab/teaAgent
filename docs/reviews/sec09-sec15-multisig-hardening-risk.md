# Reflective-Risk Report: Multi-Sig Replay + Dev-Signature Hardening (SEC-09, SEC-15)

Risk register rows SEC-09 (multi-sig approval hash) and SEC-15 (dev-hash
signatures over WAN). Date: 2026-07-01. Action IDs: S-P2-8, S-P2-9.
High-risk paths touched: `teaagent/policy.py`, `teaagent/approval/manager.py`.

## Goal

1. **SEC-09** — Eliminate the multi-sig approval-hash replay window. The hash was
   implemented in two files (`policy.py`, `approval/manager.py`); the
   `approval/manager.py` copy had already been fixed to bind the unique
   `request_id`, but the `policy.py` copy was left with the old
   `int(time.time() / 3600)` 1-hour time bucket and did **not** bind
   `request_id` — a captured peer signature was replayable for up to 59:59 within
   a window. Consolidate both into one canonical helper
   (`teaagent/approval/_multisig_crypto.py::generate_approval_hash`) that binds
   `request_id` and has no wall-clock bucket; both classes delegate.
2. **SEC-15** — Add a runtime guard so dev-hash signatures (`sha256(message +
   pubkey)`, which bypass real SSH verification) fail closed when any configured
   signature relay is non-loopback. Enforcement was previously advisory only
   (`config_lint`, `selftest`); nothing stopped a run from accepting forgeable
   signatures over a WAN relay.

## Stakeholders

Harness maintainers; the owner-operator running multi-signature quorum approval;
any federated/WAN multi-agent deployment (a wired-but-product-descoped surface);
security reviewers (this is the peer-approval trust boundary).

## Assets at Risk

- **Peer-approval integrity** — whether a high-risk operation is authorised by
  genuine, non-replayable peer signatures.
- The signed `request_hash` (the message peers sign) and its uniqueness per
  request.
- The dev-signature escape hatch (must remain loopback-only, never WAN).

## Threat Model

- **Replay (SEC-09):** an attacker who captures one valid `(peer_id, signature)`
  pair replays it to authorise a *different* high-risk request that hashes to the
  same value. With a 1-hour time bucket and no `request_id` binding, any two
  requests for the same tool/call/args within the hour collided → replayable.
- **Forgery over WAN (SEC-15):** with `TEAAGENT_ALLOW_DEV_SIGNATURES=1` (or the
  config flag) and a non-loopback relay, `sha256(message + pubkey)` — computable
  by anyone who knows the public key — is accepted as a valid signature, so any
  network party can forge quorum approvals.

## Assumption Audit

- ASSUMPTION: the `policy.py` `_check_multi_sig_quorum` path is the *only* other
  copy of the hash. VERIFIED — repo grep for `def _generate_approval_hash` and
  `time.time() / 3600` after the change returns exactly the two delegating
  methods and zero time buckets.
- ASSUMPTION: binding `request_id` (unique per request) is strictly stronger than
  and supersedes the register's "reduce 3600→300s" suggestion. VERIFIED — a
  unique per-request id makes the signed hash unique per request, so replay onto
  a different request is impossible; a shrunken time bucket would only narrow, not
  close, the window, and would additionally break verification when signature
  collection spans the bucket boundary (the collection timeout is minutes).
- ASSUMPTION: existing determinism tests that call `_generate_approval_hash`
  without `request_id` still pass. VERIFIED — the canonical helper defaults
  `request_id=''`, so same-input calls remain equal; the affected suites
  (`test_policy.py`, `test_hypothesis_invariants.py`, `test_sec_tier1_hardening.py`)
  pass unchanged.
- ASSUMPTION: the SEC-15 guard does not break loopback/dev or no-relay flows.
  VERIFIED — `resolve_allow_dev_signatures` returns `True` for loopback/no relay
  and only raises for dev-sigs + non-loopback relay; the existing non-loopback
  relay test (`test_policy.py::…`) does not enable dev signatures, and the
  fallback tests use no relay.
- ASSUMPTION: no import cycle from the new leaf. VERIFIED —
  `teaagent/approval/_multisig_crypto.py` imports only stdlib plus
  `teaagent.errors` (itself a leaf); `MultiSigQuorumConfig` is referenced under
  `TYPE_CHECKING`; `check-circular-imports` is green.

## Evidence Check

- `generate_approval_hash` binds `request_id`; `policy.py` and
  `approval/manager.py` both delegate; the `policy.py` request builder now
  computes `request_id` before hashing and passes it in.
- `resolve_allow_dev_signatures` is invoked once, before broadcast, in both
  `_collect_peer_signatures` implementations; on violation it raises the
  classified `ConfigError` (category `config`) with an actionable hint.
- New tests (all pass): `test_policy_approval_hash_binds_request_id`,
  `test_approval_hash_is_single_source_of_truth`,
  `test_approval_hash_has_no_wallclock_time_bucket`,
  `test_dev_signatures_allowed_only_on_loopback_relay`,
  `test_dev_signatures_rejected_on_non_loopback_relay`,
  `test_env_dev_signatures_rejected_on_non_loopback_relay`,
  `test_dev_signatures_not_requested_allows_real_ssh_over_wan`,
  `test_collect_peer_signatures_fails_closed_before_wan_broadcast`.
- Blast radius: the affected security/approval/governance/consensus suites ran
  green (1145 passed under a broad `-k` filter; the single failure was the
  pre-existing wall-clock `test_hybrid_approval_queue_performance` test, which is
  skipped under `-n auto` and touches an unrelated subsystem).

## Authority / Tool Boundary

- In scope: new leaf `teaagent/approval/_multisig_crypto.py`; hash + guard wiring
  in `teaagent/policy.py` and `teaagent/approval/manager.py`; new tests in
  `tests/test_sec_tier1_hardening.py`; risk-register + action-register updates.
- Out of scope: no change to `_verify_ssh_signature` internals, the SSH
  verification path, the relay transport, `MultiSigQuorumConfig` fields, or the
  approval decision/audit semantics beyond the hash content and the fail-closed
  guard.

## Failure Modes

- Over-blocking: the guard raises on a legitimate config — mitigated because it
  only fires on the genuinely-insecure combination (dev sigs + non-loopback
  relay); every other case returns a plain boolean.
- Verification mismatch: if the requester and a peer computed different hashes,
  quorum would silently fail. Not applicable — the peer signs the transmitted
  `request_hash`; the requester verifies against the same field of the same
  request object. Binding `request_id` changes the value consistently on both
  sides.

## Worst-case Scenario

A destructive operation is authorised by a replayed or forged peer signature.
Bounded by: the eight new tests plus the full approval/policy/governance/consensus
suites; a regression fails before merge. Because `request_id` is unique per
request, replay is structurally impossible, and dev-sig forgery over WAN now
raises rather than accepts.

## Safe Dry-run Plan

Pure offline verification: unit + focused security suites and an import/behaviour
sanity check (hash determinism, request_id binding, guard loopback-vs-WAN). No
production run, no network I/O, no credentials, no destructive ops.

## Rollback Plan

`git revert` the commit. The change is one new leaf module + delegation in two
methods + one guard call in two methods + tests + docs. Reverting restores the
prior behaviour exactly; no persisted-state or data migration is involved.

## Bounded Execution

Single commit; only the files listed above; no network; no destructive ops;
verified by the local suites and the pre-commit gate battery before commit.

## Audit Log Plan

No audit event is added or removed. The signed `request_hash` value changes
(now request-unique), which is a strengthening of the existing peer-signature
record, not a change to what is logged.

## Human Review Required

Yes — two high-risk paths (`teaagent/policy.py`, `teaagent/approval/manager.py`)
and the peer-approval trust boundary. This report is the reflective-risk artifact
that the `check-high-risk-paths` pre-commit hook gates on.

## Human Approval Gate

Owner instruction: "Fix all known high risks one by one." SEC-09 and SEC-15 are
the two residual register rows with a genuine, bounded, fixable gap; this closes
both. The remaining residuals are triaged below.

## Residual Risk Triage (not fixed here — why)

Per the owner request, every residual register row was triaged:

- **SEC-08** (directory-snapshot has no OS isolation, High/6): already at
  remediation ceiling — `_isolation.py` logs a warning and requires
  `acknowledge_no_os_isolation=True` for untrusted content (G-P2-1). The residual
  (no process isolation in that mode) is accepted by design; the fix is "use
  docker isolation." No further bounded code.
- **SEC-11** (undo does not reverse shell mutations, High/6): at ceiling — CLI +
  TUI emit `PARTIAL_UNDO_SHELL_WARNING`. Shell side-effects are non-recoverable
  by design (S-P2-6). No further bounded code.
- **SEC-03** (allow_all_destructive bypass, Medium/3): verified there is **no**
  `.teaagent/config` parse path for `allow_all_destructive`; it is only settable
  programmatically, prompt mode hard-denies it, and broad bypass requires an
  explicit `--permission-mode danger-full-access`. The STRIDE T-4 "config
  persistence" concern is moot. Residual WATCH is a non-security entry-ceremony
  nicety.
- **SEC-05** (adapter-reported cost injectable, Medium/3): the authoritative
  `usage_reader` mitigation is in place; fully closing the residual (a malicious
  adapter reporting `cost=0`) requires moving cost accounting to a tamper-resistant
  side-channel — an architecture change (register P3, "design decision required").
  Deferred pending an ADR; not a bounded change.
- **SEC-14** (inert `preapproved_call_ids`, Info/1): the field is deprecated and
  ignored; full removal is a next-major API break (G-P2-2 tracks the deprecation).
  Deferred by version policy.
- **SEC-NEW1/NEW2/NEW3** (Ed25519 agent identity, prompt-injection detection,
  per-deployment behavioural contracts): each is a new multi-week module and is
  only required for production/compliance/WAN deployments, which the harness-first
  direction (`docs/strategy/harness-first-direction-2026-06-13.md`) has descoped
  from current truth. Backlog; each needs its own ADR before implementation.

## Acceptance Criteria

- One canonical `generate_approval_hash` binding `request_id`; both `policy.py`
  and `approval/manager.py` delegate; no `time.time() / 3600` remains.
- `resolve_allow_dev_signatures` fails closed (`ConfigError`) for dev signatures
  over a non-loopback relay, enforced before broadcast in both quorum paths.
- All existing approval/policy/governance/consensus tests pass unchanged; the
  eight new SEC-09/SEC-15 tests pass.
- Risk register SEC-09 and SEC-15 rows show FIXED with test evidence; action
  register S-P2-8/S-P2-9 recorded.

## Go / No-go Decision

**GO** — bounded, well-tested security hardening that strictly narrows attack
surface (replay eliminated, WAN dev-sig forgery fails closed), leaves the common
loopback/local flows unchanged, and is trivially reversible.
