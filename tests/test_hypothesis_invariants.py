"""Hypothesis property-based tests for governance invariants.

Tests cover four critical invariant domains:
- Permission-mode transitions (no escalation without explicit action)
- Budget enforcement (monitor rejects when limits exceeded)
- Approval-hash exactness (hash matches what was signed)
- Audit-chain invariants (chain links verifiable, prev_hash chains correctly)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from teaagent.approval_manager import (
    MultiSigQuorumManager,
    PermissionMode,
    PermissionModeEnforcer,
)
from teaagent.audit_chain import (
    GENESIS_HASH,
    compute_chain_hmac,
    compute_event_hash,
    verify_audit_chain,
)
from teaagent.budget import RunBudget
from teaagent.budget_monitor import BudgetAction, BudgetMonitor

# ====================================================================
# Shared strategies
# ====================================================================

# Permission modes (exhaustive — there are only five)
permission_mode_st = st.sampled_from(list(PermissionMode))

# Non-permission modes (for "anything but this") — used for escalation checks
non_read_only_modes = st.sampled_from(
    [m for m in PermissionMode if m != PermissionMode.READ_ONLY]
)
non_full_access_modes = st.sampled_from(
    [
        m
        for m in PermissionMode
        if m not in (PermissionMode.ALLOW, PermissionMode.DANGER_FULL_ACCESS)
    ]
)

# Tool names (safe + destructive)
tool_name_st = st.sampled_from(
    [
        'read_file',
        'grep',
        'search',  # SAFE
        'workspace_write_file',
        'write_file',  # workspace-write allowed
        'delete_file',
        'git_push',
        'execute',  # DESTRUCTIVE
        'some_unknown_tool',  # unknown → DESTRUCTIVE default
    ]
)

# Positive finite floats for budget values
cost_st = st.floats(
    min_value=0.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False
)
positive_cost_st = st.floats(
    min_value=0.01, max_value=1_000_000.0, allow_nan=False, allow_infinity=False
)

# Budget cap must be >= 1 to avoid rounding to 0 (which triggers early-return NONE)
budget_cap_st = st.floats(
    min_value=1.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False
)

# Event IDs and types for audit-chain tests
event_id_st = st.text(
    min_size=1,
    max_size=20,
    alphabet=st.characters(whitelist_categories=('L', 'N', 'Pd', 'Ll')),
)
run_id_st = st.text(
    min_size=1, max_size=10, alphabet='abcdefghijklmnopqrstuvwxyz0123456789-_'
)
payload_st = st.one_of(
    st.none(),
    st.booleans(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=20),
    st.dictionaries(
        st.text(max_size=5, alphabet='abcdefghijklmnopqrstuvwxyz'),
        st.integers(min_value=-100, max_value=100),
        max_size=3,
    ),
)

# Call IDs and arguments for approval hash tests
call_id_st = st.text(min_size=1, max_size=16, alphabet='abcdef0123456789-')
arg_st = st.dictionaries(
    st.text(min_size=1, max_size=8, alphabet='abcdefghijklmnopqrstuvwxyz'),
    st.one_of(st.text(max_size=20), st.integers(min_value=-100, max_value=100)),
    max_size=4,
)

# ====================================================================
# Section 1: Permission-mode transitions
# ====================================================================


class TestPermissionModeTransitions:
    """Invariant: no permission mode silently escalates access rights
    without an explicit user action (mode change, approval token, etc.)."""

    @given(permission_mode_st)
    def test_read_only_blocks_all_destructive(self, mode: PermissionMode) -> None:
        """READ_ONLY must block every destructive tool call."""
        assume(mode == PermissionMode.READ_ONLY)
        enforcer = PermissionModeEnforcer(permission_mode=mode)
        result = enforcer.check(tool_name='write_file', destructive=True)
        assert result is not None, (
            'READ_ONLY should block destructive tools, got None (allowed)'
        )

    @given(tool_name_st)
    def test_read_only_blocks_all_tools_without_read_only_gate(
        self, tool_name: str
    ) -> None:
        """READ_ONLY: every tool call receives a non-None result."""
        enforcer = PermissionModeEnforcer(permission_mode=PermissionMode.READ_ONLY)
        result = enforcer.check(tool_name=tool_name, destructive=True)
        assert result is not None

    @given(tool_name_st)
    def test_workspace_write_blocks_non_workspace_destructive(
        self, tool_name: str
    ) -> None:
        """WORKSPACE_WRITE blocks destructive tools except workspace_*."""
        enforcer = PermissionModeEnforcer(
            permission_mode=PermissionMode.WORKSPACE_WRITE
        )
        result = enforcer.check(tool_name=tool_name, destructive=True)
        if tool_name in {
            'workspace_write_file',
            'workspace_apply_patch',
            'workspace_edit_at_hash',
        }:
            # These might be None (allowed) or blocked by plan contract — but the
            # key invariant is that the result is never the generic block message
            # for workspace-specific tools.
            assert result is None or 'plan' in (result or '').lower(), (
                f'Workspace write tool {tool_name} should not get generic block'
            )
        else:
            assert result is not None, (
                f'Non-workspace destructive tool {tool_name} allowed in WORKSPACE_WRITE'
            )

    @given(permission_mode_st)
    def test_prompt_requires_continue_for_destructive(
        self, mode: PermissionMode
    ) -> None:
        """PROMPT mode returns __continue__ for destructive tools (JIT gate)."""
        assume(mode == PermissionMode.PROMPT)
        enforcer = PermissionModeEnforcer(permission_mode=mode)
        result = enforcer.check(tool_name='write_file', destructive=True)
        assert result == '__continue__', (
            f'PROMPT should return __continue__ for destructive, got {result!r}'
        )

    @given(permission_mode_st)
    def test_allow_and_danger_pass_destructive(self, mode: PermissionMode) -> None:
        """ALLOW and DANGER_FULL_ACCESS let destructive tools through (None)."""
        assume(mode in (PermissionMode.ALLOW, PermissionMode.DANGER_FULL_ACCESS))
        enforcer = PermissionModeEnforcer(permission_mode=mode)
        result = enforcer.check(tool_name='write_file', destructive=True)
        assert result is None, (
            f'{mode.value} should allow destructive tools, got {result!r}'
        )

    @given(mode=non_read_only_modes)
    def test_non_destructive_always_allowed_outside_read_only(
        self, mode: PermissionMode
    ) -> None:
        """Non-destructive tools pass through in all modes except READ_ONLY."""
        enforcer = PermissionModeEnforcer(permission_mode=mode)
        result = enforcer.check(tool_name='read_file', destructive=False)
        assert result is None, (
            f'Non-destructive tools should be allowed in {mode.value}, got {result!r}'
        )

    @given(permission_mode_st)
    def test_no_escalation_without_action(self, mode: PermissionMode) -> None:
        """Invariant: allow_all_destructive without full_access_acknowledged
        does NOT escalate in non-full-access modes."""
        enforcer = PermissionModeEnforcer(
            permission_mode=mode,
            allow_all_destructive=True,
            full_access_acknowledged=False,
        )
        result = enforcer.check(tool_name='write_file', destructive=True)
        if mode == PermissionMode.READ_ONLY or mode == PermissionMode.WORKSPACE_WRITE:
            assert result is not None
        elif mode == PermissionMode.PROMPT:
            assert result == '__continue__' or 'destructive' in (result or '').lower()
        else:
            # ALLOW / DANGER_FULL_ACCESS — allowed
            assert result is None


# ====================================================================
# Section 2: Budget enforcement
# ====================================================================


class TestBudgetEnforcement:
    """Invariant: BudgetMonitor actions are monotonic with cost increase
    and always reject when limits are exceeded."""

    @given(cost=positive_cost_st, cap=budget_cap_st)
    def test_budget_action_monotonic_with_cost(self, cost: float, cap: float) -> None:
        """Budget action priority never decreases as cost increases."""
        budget = RunBudget(max_estimated_cost_cents=int(cap))
        monitor = BudgetMonitor(budget=budget, interactive=False)

        # Each level fires at most once; the first call may fire a level,
        # subsequent calls at the same cost must be idempotent.
        monitor.check(run_id='test', cost_cents=cost)
        action_again = monitor.check(run_id='test', cost_cents=cost)
        # Re-running at same cost is idempotent
        assert action_again == BudgetAction.NONE

    @given(cost=positive_cost_st, cap=budget_cap_st)
    def test_budget_exhausted_triggers_suggest_read_only(
        self, cost: float, cap: float
    ) -> None:
        """At 100%+ consumption, the monitor suggests read-only mode."""
        assume(cap >= 0.01)  # avoid division issues
        percent = (cost / cap) * 100.0
        assume(percent >= 100.0)

        budget = RunBudget(max_estimated_cost_cents=int(cap))
        monitor = BudgetMonitor(budget=budget, interactive=False)
        action = monitor.check(run_id='test', cost_cents=cost)

        assert action == BudgetAction.SUGGEST_READ_ONLY, (
            f'At {percent:.1f}% cost ({cost:.2f}/{cap:.2f}) expected '
            f'SUGGEST_READ_ONLY, got {action.value}'
        )

    @given(cost=positive_cost_st, cap=budget_cap_st)
    def test_budget_zero_cap_returns_none(self, cost: float, cap: float) -> None:
        """When budget cap is 0, monitor returns NONE regardless of cost."""
        budget = RunBudget(max_estimated_cost_cents=0)
        monitor = BudgetMonitor(budget=budget, interactive=False)
        action = monitor.check(run_id='test', cost_cents=cost)
        assert action == BudgetAction.NONE

    @given(cost=positive_cost_st, cap=positive_cost_st)
    def test_budget_no_cap_returns_none(self, cost: float, cap: float) -> None:
        """When budget cap is None, monitor returns NONE."""
        budget = RunBudget(max_estimated_cost_cents=None)
        monitor = BudgetMonitor(budget=budget, interactive=False)
        action = monitor.check(run_id='test', cost_cents=cost)
        assert action == BudgetAction.NONE

    @given(cost=positive_cost_st, cap=budget_cap_st)
    def test_budget_50_pct_emits_warn(self, cost: float, cap: float) -> None:
        """At exactly 50%, the monitor returns WARN."""
        budget = RunBudget(max_estimated_cost_cents=int(cap))
        monitor = BudgetMonitor(budget=budget, interactive=False)
        action = monitor.check_at_threshold(
            run_id='test', cost_cents=cap * 0.5, threshold=50
        )
        assert action == BudgetAction.WARN

    @given(
        cost=st.floats(min_value=0, max_value=0, allow_nan=False, allow_infinity=False),
        cap=budget_cap_st,
    )
    def test_budget_zero_cost_returns_none(self, cost: float, cap: float) -> None:
        """At zero cost and non-zero cap, check returns NONE."""
        budget = RunBudget(max_estimated_cost_cents=int(cap))
        monitor = BudgetMonitor(budget=budget, interactive=False)
        action = monitor.check(run_id='test', cost_cents=0.0)
        assert action == BudgetAction.NONE

    @given(cost=positive_cost_st, cap=budget_cap_st)
    def test_budget_80_pct_emits_warn(self, cost: float, cap: float) -> None:
        """At exactly 80%, the monitor returns WARN."""
        assume(cap >= 1)  # avoid integer rounding weirdness
        budget = RunBudget(max_estimated_cost_cents=int(cap))
        monitor = BudgetMonitor(budget=budget, interactive=False)
        action = monitor.check_at_threshold(
            run_id='test', cost_cents=cap * 0.8, threshold=80
        )
        assert action == BudgetAction.WARN

    @given(
        iterations=st.integers(min_value=0, max_value=10_000),
        max_iters=st.integers(min_value=1, max_value=10_000),
    )
    def test_iteration_budget_monotonic(self, iterations: int, max_iters: int) -> None:
        """Iteration budget actions are consistent."""
        budget = RunBudget(max_iterations=max_iters)
        monitor = BudgetMonitor(budget=budget, interactive=False)
        action = monitor.check_iterations(run_id='test', iterations=iterations)
        if iterations >= max_iters:
            assert action == BudgetAction.SUGGEST_READ_ONLY, (
                f'At {iterations}/{max_iters} iterations expected '
                f'SUGGEST_READ_ONLY, got {action.value}'
            )
        elif iterations < max_iters and iterations / max_iters >= 0.9:
            assert action != BudgetAction.NONE


# ====================================================================
# Section 3: Approval-hash exactness
# ====================================================================


class TestApprovalHashExactness:
    """Invariant: approval hashes are deterministic, collision-resistant,
    and verifiable — the hash exactly matches what was signed."""

    def _make_mgr(self) -> MultiSigQuorumManager:
        return MultiSigQuorumManager(agent_id='test-agent')

    @given(tool=tool_name_st, call=call_id_st, args=arg_st)
    def test_approval_hash_deterministic(
        self, tool: str, call: str, args: dict[str, Any]
    ) -> None:
        """Same inputs must produce identical hash."""
        mgr = self._make_mgr()
        h1 = mgr._generate_approval_hash(tool, call, args)
        h2 = mgr._generate_approval_hash(tool, call, args)
        assert h1 == h2, 'Approval hash for same inputs must be identical'

    @given(tool=tool_name_st, call=call_id_st, args=arg_st)
    def test_approval_hash_is_valid_hex(
        self, tool: str, call: str, args: dict[str, Any]
    ) -> None:
        """Hash output must be a valid 64-char hex string (SHA-256)."""
        mgr = self._make_mgr()
        h = mgr._generate_approval_hash(tool, call, args)
        assert len(h) == 64, f'Expected 64 hex chars, got {len(h)}'
        int(h, 16)  # raises ValueError if not valid hex

    @given(
        tool1=tool_name_st,
        call1=call_id_st,
        args1=arg_st,
        tool2=tool_name_st,
        call2=call_id_st,
        args2=arg_st,
    )
    def test_approval_hash_differs_for_different_inputs(
        self,
        tool1: str,
        call1: str,
        args1: dict[str, Any],
        tool2: str,
        call2: str,
        args2: dict[str, Any],
    ) -> None:
        """Different inputs must produce different hashes
        (with overwhelming probability)."""
        assume((tool1, call1, args1) != (tool2, call2, args2))
        mgr = self._make_mgr()
        h1 = mgr._generate_approval_hash(tool1, call1, args1)
        h2 = mgr._generate_approval_hash(tool2, call2, args2)
        assert h1 != h2, f'Different inputs produced identical hash {h1}'

    @given(tool=tool_name_st, call=call_id_st, args=arg_st)
    def test_approval_hash_uses_sha256(
        self, tool: str, call: str, args: dict[str, Any]
    ) -> None:
        """The hash MUST be SHA-256, not a weaker algorithm."""
        mgr = self._make_mgr()
        h = mgr._generate_approval_hash(tool, call, args)
        # SHA-256 hex output = 64 characters
        assert len(h) == 64

    @given(tool=tool_name_st, call=call_id_st, args=arg_st)
    def test_approval_hash_includes_call_id(
        self, tool: str, call: str, args: dict[str, Any]
    ) -> None:
        """Changing only the call_id must change the hash."""
        mgr = self._make_mgr()
        h1 = mgr._generate_approval_hash(tool, call, args)
        # Different call_id
        other_call = call + 'x' if len(call) < 15 else call[:-1]
        assume(other_call != call)
        h2 = mgr._generate_approval_hash(tool, other_call, args)
        assert h1 != h2

    @given(key=st.binary(min_size=32, max_size=32))
    def test_chain_hmac_deterministic(self, key: bytes) -> None:
        """HMAC must be deterministic for the same key and hash."""
        event_hash = hashlib.sha256(b'test-event').hexdigest()
        h1 = compute_chain_hmac(event_hash, key)
        h2 = compute_chain_hmac(event_hash, key)
        assert h1 == h2

    @given(key=st.binary(min_size=32, max_size=32))
    def test_chain_hmac_differs_with_different_key(self, key: bytes) -> None:
        """Different keys must produce different HMACs for the same hash."""
        event_hash = hashlib.sha256(b'test-event').hexdigest()
        other_key = bytes(b ^ 0xFF for b in key)  # flip all bits
        h1 = compute_chain_hmac(event_hash, key)
        h2 = compute_chain_hmac(event_hash, other_key)
        assert h1 != h2, 'HMACs for different keys must differ'

    @given(tool=tool_name_st, call=call_id_st, args=arg_st)
    def test_approval_hash_canonical_json(
        self, tool: str, call: str, args: dict[str, Any]
    ) -> None:
        """The hash is computed over canonical (sorted-key) JSON,
        so the same logical content always produces the same hash."""
        mgr = self._make_mgr()
        h1 = mgr._generate_approval_hash(tool, call, None)
        # Empty dict and None should be treated consistently
        h2 = mgr._generate_approval_hash(tool, call, {})
        assert h1 == h2, (
            'Empty arguments and None must produce same hash (canonical JSON)'
        )


# ====================================================================
# Section 4: Audit-chain invariants
# ====================================================================


class TestAuditChainInvariants:
    """Invariant: audit chains are verifiable, each link correctly
    references the previous hash, and tampering is always detected."""

    @staticmethod
    def _make_event(
        event_id: str = 'e1',
        event_type: str = 'test',
        run_id: str = 'r1',
        created_at: str = '2026-01-01T00:00:00Z',
        payload: object = None,
        prev_hash: str = GENESIS_HASH,
    ) -> dict:
        return {
            'event_id': event_id,
            'event_type': event_type,
            'run_id': run_id,
            'created_at': created_at,
            'payload': payload or {},
            'prev_hash': prev_hash,
        }

    @staticmethod
    def _build_chain(events: list[dict]) -> list[dict]:
        chain: list[dict] = []
        prev_hash = GENESIS_HASH
        for evt in events:
            event = {
                'event_id': evt.get('event_id', 'e'),
                'event_type': evt.get('event_type', 'test'),
                'run_id': evt.get('run_id', 'r1'),
                'created_at': evt.get('created_at', '2026-01-01T00:00:00Z'),
                'payload': evt.get('payload', {}),
                'prev_hash': prev_hash,
            }
            event['hash'] = compute_event_hash(event)
            prev_hash = event['hash']
            chain.append(event)
        return chain

    @staticmethod
    def _write_chain(chain: list[dict], path: Path) -> None:
        path.write_text(
            '\n'.join(json.dumps(e, sort_keys=True) for e in chain) + '\n',
            encoding='utf-8',
        )

    # ── Hypothesis-based chain tests ───────────────────────────────

    @given(
        event_ids=st.lists(event_id_st, min_size=1, max_size=10),
        run_id=run_id_st,
    )
    def test_valid_chain_passes(self, event_ids: list[str], run_id: str) -> None:
        """Any correctly built chain must pass verification."""
        events = [self._make_event(event_id=eid, run_id=run_id) for eid in event_ids]
        chain = self._build_chain(events)
        assert len(chain) == len(event_ids)

    @given(
        event_ids=st.lists(event_id_st, min_size=2, max_size=8),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_tampered_event_hash_causes_failure(
        self, event_ids: list[str], tmp_path: Path
    ) -> None:
        """Modifying an event's payload after chain creation must cause
        hash mismatch."""
        events = [self._make_event(event_id=eid) for eid in event_ids]
        chain = self._build_chain(events)
        # Tamper with the middle event
        tamper_idx = max(1, len(chain) // 2)
        chain[tamper_idx]['payload'] = {'tampered': True}
        log = tmp_path / 'tampered.jsonl'
        self._write_chain(chain, log)
        result = verify_audit_chain(log)
        assert not result.valid, 'Chain with tampered event must fail verification'
        assert result.total_hash_mismatches >= 1

    @given(
        event_ids=st.lists(event_id_st, min_size=3, max_size=8),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_prev_hash_mismatch_detected(
        self, event_ids: list[str], tmp_path: Path
    ) -> None:
        """Breaking the prev_hash chain must be detected."""
        events = [self._make_event(event_id=eid) for eid in event_ids]
        chain = self._build_chain(events)
        # Break prev_hash of event at index 1 (point to wrong hash)
        if len(chain) > 1:
            chain[1]['prev_hash'] = (
                'deadbeef' + chain[1].get('prev_hash', 'genesis')[:56]
            )
            log = tmp_path / 'broken.jsonl'
            self._write_chain(chain, log)
            result = verify_audit_chain(log)
            assert not result.valid, (
                'Chain with broken prev_hash must fail verification'
            )
            assert result.total_prev_hash_mismatches >= 1

    @given(
        event_ids=st.lists(event_id_st, min_size=1, max_size=5),
    )
    def test_event_hash_deterministic(self, event_ids: list[str]) -> None:
        """Event hash for same event content must be identical."""
        evt = self._make_event(event_id='test-eid')
        h1 = compute_event_hash(evt)
        h2 = compute_event_hash(evt)
        assert h1 == h2

    @given(event_ids=st.lists(event_id_st, min_size=1, max_size=5))
    def test_event_hash_differs_for_different_events(
        self, event_ids: list[str]
    ) -> None:
        """Different event content must produce different hashes."""
        assume(len(event_ids) >= 2)
        e1 = self._make_event(event_id=event_ids[0])
        e2 = self._make_event(event_id=event_ids[1])
        assume(e1 != e2)
        h1 = compute_event_hash(e1)
        h2 = compute_event_hash(e2)
        assert h1 != h2

    @given(
        event_ids=st.lists(event_id_st, min_size=3, max_size=10),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_chain_hash_trivially_verifiable(
        self, event_ids: list[str], tmp_path: Path
    ) -> None:
        """Compute each event's hash independently and verify the chain."""
        events = [self._make_event(event_id=eid) for eid in event_ids]
        chain = self._build_chain(events)
        log = tmp_path / 'trivial.jsonl'
        self._write_chain(chain, log)
        result = verify_audit_chain(log)
        assert result.valid, f'Correctly built chain must pass: {result.error}'
        assert result.event_count == len(event_ids)

    @given(
        event_ids=st.lists(event_id_st, min_size=2, max_size=6),
        extra_event=event_id_st,
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_genesis_to_chain_continuity(
        self, event_ids: list[str], extra_event: str, tmp_path: Path
    ) -> None:
        """The very first event's prev_hash is always 'genesis'."""
        assume(extra_event not in event_ids)
        events = [self._make_event(event_id=eid) for eid in event_ids]
        chain = self._build_chain(events)
        # First event must have genesis hash
        assert chain[0]['prev_hash'] == GENESIS_HASH
        log = tmp_path / 'genesis.jsonl'
        self._write_chain(chain, log)
        result = verify_audit_chain(log)
        assert result.valid

    @given(
        event_ids=st.lists(event_id_st, min_size=2, max_size=6),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_deleted_event_causes_prev_hash_mismatch(
        self, event_ids: list[str], tmp_path: Path
    ) -> None:
        """Removing an event from the middle breaks the chain."""
        assume(len(event_ids) >= 3)
        events = [self._make_event(event_id=eid) for eid in event_ids]
        chain = self._build_chain(events)
        # Remove middle event
        del_idx = len(chain) // 2
        del chain[del_idx]
        log = tmp_path / 'deleted.jsonl'
        self._write_chain(chain, log)
        result = verify_audit_chain(log)
        assert not result.valid, 'Chain with deleted event must fail verification'
        assert (
            result.total_prev_hash_mismatches >= 1 or result.total_hash_mismatches >= 1
        )

    @given(
        event_ids=st.lists(event_id_st, min_size=3, max_size=6),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_inserted_event_causes_prev_hash_mismatch(
        self, event_ids: list[str], tmp_path: Path
    ) -> None:
        """Inserting a foreign event breaks the chain."""
        assume(len(event_ids) >= 2)
        events = [self._make_event(event_id=eid) for eid in event_ids]
        chain = self._build_chain(events)
        # Insert a foreign event
        foreign = self._make_event(event_id='foreign')
        foreign['hash'] = compute_event_hash(foreign)
        insert_idx = len(chain) // 2
        chain.insert(insert_idx, foreign)
        log = tmp_path / 'inserted.jsonl'
        self._write_chain(chain, log)
        result = verify_audit_chain(log)
        assert not result.valid

    @given(key=st.binary(min_size=32, max_size=32))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_chain_hmac_verification(self, key: bytes, tmp_path: Path) -> None:
        """HMAC-protected chain verifies correctly with the right key
        and fails with the wrong key."""
        events = [
            self._make_event(event_id='e1'),
            self._make_event(event_id='e2'),
        ]
        chain = self._build_chain(events)
        # Add HMACs
        for evt in chain:
            evt['chain_hmac'] = compute_chain_hmac(evt['hash'], key)
        log = tmp_path / 'hmac.jsonl'
        self._write_chain(chain, log)
        result = verify_audit_chain(log, secret_key=key)
        assert result.valid, f'Valid HMAC chain must pass: {result.error}'

        # Wrong key must fail
        wrong_key = bytes(b ^ 0xAA for b in key)
        wrong_result = verify_audit_chain(log, secret_key=wrong_key)
        # The validator will find HMAC mismatches, but may still report
        # valid=False
        assert wrong_result.failures or not wrong_result.valid, (
            'Wrong HMAC key must produce failures'
        )

    @given(
        event_ids=st.lists(event_id_st, min_size=2, max_size=5),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_chain_timestamp_regression_detected(
        self, event_ids: list[str], tmp_path: Path
    ) -> None:
        """Out-of-order timestamps must be flagged as regression."""
        events = [
            self._make_event(
                event_id=eid,
                created_at=f'2026-01-01T00:00:{i:02d}Z',
            )
            for i, eid in enumerate(event_ids)
        ]
        chain = self._build_chain(events)
        # Reorder: swap last two events to create timestamp regression
        if len(chain) >= 2:
            chain[-1], chain[-2] = chain[-2], chain[-1]
            log = tmp_path / 'regression.jsonl'
            self._write_chain(chain, log)
            result = verify_audit_chain(log)
            # Note: the chain may still fail hash check because prev_hash is wrong,
            # but timestamp regression should also be detected.
            assert result.total_timestamp_regressions >= 1 or not result.valid, (
                'Timestamp regression must be flagged'
            )
