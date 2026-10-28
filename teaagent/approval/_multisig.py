"""Multi-signature quorum for high-risk tool calls (peer SSH signatures).

Moved unchanged from ``teaagent.approval.manager`` (A-P1-6 split, ADR-0044).
``teaagent.approval.manager`` re-exports every name. The logger keeps its
established name, ``teaagent.approval_manager``, so operator tooling and
caplog assertions do not change.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from teaagent.approval._shell_normalize import _normalize_shell_arg

logger = logging.getLogger('teaagent.approval_manager')


@dataclass(frozen=True)
class PeerSignature:
    """Cryptographic signature from a peer developer for multi-sig approval."""

    peer_id: str
    signature: str
    timestamp: float
    ssh_key_id: Optional[str] = None


@dataclass(frozen=True)
class MultiSigQuorumConfig:
    """Configuration for multi-signature quorum governance."""

    enabled: bool = False
    required_approvals: int = 2
    peer_agent_ids: list[str] = field(default_factory=list)
    peer_public_keys: dict[str, str] = field(default_factory=dict)
    peer_relay_urls: dict[str, str] = field(default_factory=dict)
    local_relay_base_url: str | None = None
    allow_dev_signatures: bool = False
    high_risk_patterns: list[str] = field(default_factory=list)
    timeout_seconds: int = 300

    @classmethod
    def from_workspace_config(cls, root: str | Path) -> MultiSigQuorumConfig:
        """Load ``multi_sig`` section from ``<root>/.teaagent/config.json``."""
        from teaagent.config_loader import load_workspace_config

        section = load_workspace_config(root).get('multi_sig')
        if not isinstance(section, dict):
            return cls()

        peer_ids = section.get('peer_agent_ids') or []
        if not isinstance(peer_ids, list):
            peer_ids = []

        patterns = section.get('high_risk_patterns') or []
        if not isinstance(patterns, list):
            patterns = []

        relay_urls = section.get('peer_relay_urls') or {}
        if not isinstance(relay_urls, dict):
            relay_urls = {}

        public_keys = section.get('peer_public_keys') or {}
        if not isinstance(public_keys, dict):
            public_keys = {}

        local_relay = section.get('local_relay_base_url')
        local_relay_url = str(local_relay).strip() if local_relay else None
        if local_relay_url == '':
            local_relay_url = None

        return cls(
            enabled=bool(section.get('enabled', False)),
            required_approvals=int(section.get('required_approvals', 2)),
            peer_agent_ids=[str(item) for item in peer_ids],
            peer_public_keys={str(k): str(v) for k, v in public_keys.items()},
            peer_relay_urls={str(k): str(v).rstrip('/') for k, v in relay_urls.items()},
            local_relay_base_url=local_relay_url,
            allow_dev_signatures=bool(section.get('allow_dev_signatures', False)),
            high_risk_patterns=[str(item) for item in patterns],
            timeout_seconds=int(section.get('timeout_seconds', 300)),
        )


@dataclass(frozen=True)
class PeerApprovalRequest:
    """Request for peer approval broadcast via P2P sync."""

    request_id: str
    tool_name: str
    call_id: str
    arguments: dict[str, Any]
    request_hash: str
    timestamp: float
    requester_agent_id: str
    signatures: list[PeerSignature] = field(default_factory=list)


# Deprecated alias (A-P1-8, owner decision Q4): the P2P request was renamed to
# PeerApprovalRequest because two other classes are also named ApprovalRequest
# (approval.backend and runner._types). This name is the same class object.
# Plain alias: this module has no module-level __getattr__ deprecation pattern.
ApprovalRequest = PeerApprovalRequest


class MultiSigQuorumManager:
    """Manages multi-signature quorum for high-risk operations (ADR-002)."""

    def __init__(
        self,
        config: MultiSigQuorumConfig | None = None,
        agent_id: str = '',
        *,
        audit: Any | None = None,
        origin_run_id: str = '',
    ) -> None:
        self.config = config or MultiSigQuorumConfig()
        self.agent_id = agent_id
        # Optional audit sink (duck-typed AuditLogger). When present, governance
        # fallbacks are written to the audit chain (G-P1-3) in addition to logs.
        self._audit = audit
        self._origin_run_id = origin_run_id
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix='sig-collect'
        )

    def _audit_event(self, event_type: str, **payload: Any) -> None:
        """Best-effort emit to the audit chain; never affects the gate decision."""
        if self._audit is None:
            return
        try:
            self._audit.record(event_type, self._origin_run_id or '', **payload)
        except Exception:  # pragma: no cover - audit must never break approval
            logger.warning('Failed to record %s audit event', event_type)

    def is_high_risk(self, tool_name: str, arguments: dict[str, Any] | None) -> bool:
        if not self.config.high_risk_patterns:
            return False
        tool_lower = tool_name.lower()
        for pattern in self.config.high_risk_patterns:
            if pattern.lower() in tool_lower:
                return True
        if arguments:
            for _key, value in arguments.items():
                if isinstance(value, str):
                    # Normalize the string value to defeat shell obfuscation before
                    # pattern matching.
                    normalized_value = _normalize_shell_arg(value)
                    raw_value = value.lower()
                    for pattern in self.config.high_risk_patterns:
                        pat_lower = pattern.lower()
                        if pat_lower in raw_value or pat_lower in normalized_value:
                            return True
        return False

    def check_quorum(
        self,
        tool_name: str,
        call_id: str,
        arguments: dict[str, Any] | None,
    ) -> bool:
        """Check multi-signature quorum for high-risk operations.

        Returns:
            True if quorum is reached and operation is approved, False otherwise.
        """
        if not self.config.enabled:
            return False

        if not self.agent_id:
            logger.warning(
                'Multi-sig quorum not available: agent_id not set',
                extra={
                    'event': 'multisig_fallback',
                    'reason': 'agent_id_not_set',
                    'tool_name': tool_name,
                    'call_id': call_id,
                    'required_approvals': self.config.required_approvals,
                },
            )
            # G-P1-3: also record to the audit chain so the misconfiguration is
            # detectable after the fact, not only in process logs.
            self._audit_event(
                'multisig_fallback',
                reason='agent_id_not_set',
                tool_name=tool_name,
                call_id=call_id,
                required_approvals=self.config.required_approvals,
            )
            print(
                '[Governance] Multi-Signature Quorum enabled but agent_id not set. '
                'Falling back to standard approval.'
            )
            return False

        request_id = hashlib.sha256(
            f'{self.agent_id}{call_id}{time.time()}'.encode()
        ).hexdigest()[:16]
        request_hash = self._generate_approval_hash(
            tool_name,
            call_id,
            arguments,
            request_id=request_id,
        )
        request = PeerApprovalRequest(
            request_id=request_id,
            tool_name=tool_name,
            call_id=call_id,
            arguments=arguments or {},
            request_hash=request_hash,
            timestamp=time.time(),
            requester_agent_id=self.agent_id,
        )

        print(
            f'[Governance] Multi-Signature Quorum is enabled. '
            f'Seeking {self.config.required_approvals} peer approvals...'
        )
        print(
            f'[Broadcast...] Sending JIT signature requests to peers '
            f'{self.config.peer_agent_ids}...'
        )

        signatures = self._collect_peer_signatures(request)

        if len(signatures) >= self.config.required_approvals:
            print(
                f'[✓] Quorum Reached '
                f'({len(signatures)}/{self.config.required_approvals} approvals).'
            )
            for sig in signatures:
                print(
                    f'[{sig.peer_id}]: SIGNED '
                    f'(SSH-Key-ID: {sig.ssh_key_id or "unknown"})'
                )
            return True
        else:
            print(
                f'[✗] Quorum Not Reached '
                f'({len(signatures)}/{self.config.required_approvals} required).'
            )
            return False

    def _generate_approval_hash(
        self,
        tool_name: str,
        call_id: str,
        arguments: dict[str, Any] | None,
        *,
        request_id: str = '',
        run_id: str = '',
    ) -> str:
        """Generate the canonical approval-request hash (see _multisig_crypto)."""
        from teaagent.approval._multisig_crypto import generate_approval_hash

        return generate_approval_hash(
            tool_name, call_id, arguments, request_id=request_id, run_id=run_id
        )

    def _collect_peer_signatures(
        self, request: PeerApprovalRequest
    ) -> list[PeerSignature]:
        """Collect peer signatures for approval request.

        Integrates with federated_sync to broadcast the request via P2P sync,
        wait for peers to sign with their SSH keys, and verify signatures.
        """
        from teaagent.approval._multisig_crypto import resolve_allow_dev_signatures
        from teaagent.security_env import allow_dev_signatures as env_allow_dev

        # SEC-15: fail closed before any broadcast when dev-hash signatures
        # would be honored over a non-loopback relay (they bypass SSH auth).
        allow_dev = resolve_allow_dev_signatures(
            self.config, env_enabled=env_allow_dev()
        )

        try:
            from teaagent.federated_sync import (
                ApprovalRequestMessage,
                FederatedGraphSync,
            )
        except ImportError:
            logger.warning('Federated sync not available for multi-sig quorum')
            return []

        sync = FederatedGraphSync(
            root=str(Path.cwd()),
            agent_id=self.agent_id or 'unknown',
        )

        submit_url = None
        local_relay = self.config.local_relay_base_url
        if local_relay:
            submit_url = f'{local_relay.rstrip("/")}/api/v1/approval-signatures'

        approval_request = ApprovalRequestMessage(
            request_id=request.request_id,
            tool_name=request.tool_name,
            call_id=request.call_id,
            arguments=request.arguments or {},
            request_hash=request.request_hash,
            timestamp=request.timestamp,
            requester_agent_id=request.requester_agent_id,
            required_approvals=self.config.required_approvals,
            timeout_seconds=self.config.timeout_seconds,
            signature_submit_url=submit_url,
        )

        sync.broadcast_approval_request(
            approval_request,
            self.config.peer_agent_ids,
            peer_relay_urls=self.config.peer_relay_urls,
        )

        signature_messages = self._run_async_signature_collection(
            sync,
            request.request_id,
            required_approvals=self.config.required_approvals,
            relay_base_url=local_relay,
        )

        peer_signatures: list[PeerSignature] = []
        for sig_msg in signature_messages:
            message_to_verify = request.request_hash
            sig_age = abs(float(sig_msg.timestamp) - float(request.timestamp))
            if sig_age > float(self.config.timeout_seconds):
                print(
                    f'[Security] Rejected stale signature from peer {sig_msg.peer_id} '
                    f'(age={sig_age:.0f}s > timeout={self.config.timeout_seconds}s)'
                )
                continue
            is_valid = _verify_ssh_signature(
                signature=sig_msg.signature,
                message=message_to_verify,
                ssh_key_id=sig_msg.peer_id,
                peer_public_keys=self.config.peer_public_keys,
                allow_dev_signatures=allow_dev,
            )

            if not is_valid:
                print(
                    f'[Security] Rejected invalid signature from peer {sig_msg.peer_id}'
                )
                continue

            peer_sig = PeerSignature(
                peer_id=sig_msg.peer_id,
                signature=sig_msg.signature,
                timestamp=sig_msg.timestamp,
                ssh_key_id=sig_msg.ssh_key_id,
            )
            peer_signatures.append(peer_sig)

        return peer_signatures

    def _run_async_signature_collection(
        self,
        sync: Any,
        request_id: str,
        *,
        required_approvals: int = 1,
        relay_base_url: str | None = None,
    ) -> Any:
        """Run async signature collection without starving the event loop.

        Detects whether an event loop is active and dispatches accordingly:
        - If called from a thread with a running event loop, offloads to a
          ThreadPoolExecutor so the coroutine runs in a fresh thread with its
          own event loop.
        - Otherwise, runs the coroutine via ``asyncio.run()``.
        """
        coro = sync.collect_approval_signatures(
            request_id,
            timeout_seconds=self.config.timeout_seconds,
            required_approvals=required_approvals,
            relay_base_url=relay_base_url,
        )
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            from teaagent.async_bridge import run_coroutine_sync

            timeout = self.config.timeout_seconds + 5
            return run_coroutine_sync(
                coro,
                executor=self._executor,
                timeout_seconds=timeout,
            )
        return asyncio.run(coro)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)


# Sentinel: False until a real cryptography library is integrated.
_SSH_VERIFICATION_IMPLEMENTED = True


def _verify_ssh_signature(
    signature: str,
    message: str,
    ssh_key_id: Optional[str],
    peer_public_keys: dict[str, str],
    *,
    allow_dev_signatures: bool = False,
) -> bool:
    """Verify an SSH signature; dev-hash only when explicitly allowed."""
    import hashlib
    import secrets

    from teaagent.ssh_signatures import is_ssh_signature_blob, verify_message_ssh

    if not signature or not signature.strip():
        return False
    if not ssh_key_id or not ssh_key_id.strip():
        return False
    pubkey = peer_public_keys.get(ssh_key_id)
    if not pubkey:
        return False
    if is_ssh_signature_blob(signature):
        return verify_message_ssh(pubkey, message, signature)
    if not allow_dev_signatures:
        return False
    expected = hashlib.sha256((message + pubkey).encode()).hexdigest()
    return secrets.compare_digest(signature, expected)
