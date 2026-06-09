# SPEC — Approval Store Permission Binding (CV-8)

`SPEC_VERSION = 2026-06-09-approval-store-permission-binding-v1`
**Risk level:** **L3** (authorization / permission engine)   ·   **Status:** documenting existing behavior
**Code:** [`teaagent/ergonomics/_approval_state.py`](../../teaagent/ergonomics/_approval_state.py)
(public import: `teaagent.ergonomics.approval_store.ApprovalPresetStore`);
grant primitives in [`teaagent/ergonomics/_approval_grants.py`](../../teaagent/ergonomics/_approval_grants.py).

This is the Roadmap A2 permission-binding record for the approval engine — the module that decides
what tool calls are allowed. It does **not** add behavior; it makes the CV-8 boundary explicit and
links each Forbidden rule to the test that already guards it, so the boundary is auditable and
regression-protected.

## Goal / Non-goals
- **Goal:** state, in one place, what the approval store is allowed to grant, what it must refuse, and
  which changes require human review — and bind each rule to a guard test.
- **Non-goals:** no change to grant semantics, TTLs, or the digest scheme.

## Allowed / Forbidden / Requires Human Review (CV-8)

- **Allowed:**
  - Create a **scoped** approval bound to `(run_id, call_id, tool_name, argument_digest)`.
  - Create a `session`-scope grant with empty `path_globs` (explicitly unrestricted, labelled
    `unrestricted (all paths)` via `ApprovalGrant.path_scope_label`).
  - Grant `once` / `always` / `session` with **explicit** path globs or command prefixes.
  - Consume a scoped approval whose recomputed digest (HMAC v2 or legacy v1) matches.

- **Forbidden** (each must stay refused):
  - **F1 — implicit global grant from empty patterns.** `path_globs=[]` / `['']` / whitespace for any
    non-session scope must raise, not silently become an all-paths grant.
    Guard: `tests/integration/test_destructive_approval_lifecycle.py::test_empty_path_globs_rejected_ds12`.
  - **F2 — `deny` / persistent scope without explicit patterns.** `deny(...)` or `always`/`once` with
    `path_globs=None` and `command_prefixes=None` must raise (`must be provided explicitly`).
    Guard: `tests/integration/test_destructive_approval_lifecycle.py::test_approval_policy_rejects_empty_path`.
  - **F3 — consuming a scoped approval under a non-matching digest.** A different/tampered argument set
    yields a different digest and must not consume the approval.
    Guard: `tests/test_approval_token_exactness.py::test_mismatched_arguments_reject_scoped_token`,
    `tests/test_approval_token_exactness.py::test_hmac_argument_digest_rejects_tampered_store`, and
    SURF-010 `test_resume_preparation.py::test_auto_grant_is_bound_to_exact_digest`.
  - **F4 — path traversal widening.** `../` or symlink-escaping paths must not match a scoped glob
    (`_normalize_and_validate_path` returns None → no match).

- **Requires Human Review:** any change to `_normalize_grant_patterns`, `grant`/`deny` scope rules,
  `_compute_argument_digest`, `try_consume_scoped_approval` / `check_scoped_approval`, or the
  path-traversal validation in `_normalize_and_validate_path`.

## Real-world Assumptions (CV-4)
- Grants persist to disk and outlive a single process; an over-broad grant is a standing risk until it
  expires (`APPROVAL_TTL_HOURS = 24h`) or is revoked.
- Legacy v1 digests exist on disk; the consume path must accept v1 **and** v2 without widening scope.

## Verification
The Forbidden rules above are enforced by the named guard tests (run in CI). This spec is covered by
the structural meta-test `tests/test_governance_permission_binding.py`, which fails if an L3 trust
module loses its permission-binding spec or its Forbidden / Requires-Human-Review sections.

---

## Spec Quality Gate
- [x] Goal single & verifiable; Non-goals explicit
- [x] Forbidden behaviors listed and each bound to a guard test
- [x] P0/L3 risk classified (authorization engine)
- [x] Human-review trigger present
- [x] No mutually contradictory conditions
- [x] Real-world assumptions stated (persistence, legacy digests)
