"""Federated graph sync protocol for multi-agent collaboration.

This module provides FederatedGraphSync for synchronizing code ontology
graphs across multiple TeaAgent instances, enabling collaborative code
intelligence with conflict resolution and incremental updates.
"""

from __future__ import annotations

import contextlib
import functools
import hashlib
import json
import logging
import socket
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from teaagent.graphqlite_store import GraphQLiteGraphStore
from teaagent.security_env import federated_signature_token, signature_relay_api_token
from teaagent.storage import atomic_write_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GraphChange:
    """Represents a single change to the graph."""

    change_id: str
    timestamp: float
    node_id: Optional[str] = None
    edge_id: Optional[str] = None
    change_type: str = (
        ''  # "node_add", "node_update", "node_delete", "edge_add", "edge_delete"
    )
    data: dict[str, Any] = field(default_factory=dict)
    source_agent_id: str = ''


@dataclass(frozen=True)
class SyncMessage:
    """Message sent between agents for graph synchronization."""

    message_id: str
    sender_agent_id: str
    timestamp: float
    changes: list[GraphChange]
    sequence_number: int
    graph_version: str


@dataclass(frozen=True)
class SyncAck:
    """Acknowledgment message for sync confirmation."""

    message_id: str
    receiver_agent_id: str
    timestamp: float
    accepted_changes: list[str]
    rejected_changes: list[str]
    conflicts: list[str]


@dataclass(frozen=True)
class SyncState:
    """Current synchronization state for an agent."""

    agent_id: str
    graph_version: str
    last_sync_time: float
    sequence_number: int
    peer_states: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class ApprovalRequestMessage:
    """Message for multi-sig approval requests broadcast via P2P sync."""

    request_id: str
    tool_name: str
    call_id: str
    arguments: dict[str, Any]
    request_hash: str
    timestamp: float
    requester_agent_id: str
    required_approvals: int
    timeout_seconds: int
    signature_submit_url: Optional[str] = None


@dataclass(frozen=True)
class ApprovalSignatureMessage:
    """Message for peer signature responses."""

    request_id: str
    peer_id: str
    signature: str
    ssh_key_id: Optional[str] = None
    timestamp: float = 0.0


class FederatedGraphSync:
    """Manages federated synchronization of code ontology graphs."""

    def __init__(
        self,
        root: str | Path,
        agent_id: str,
        graph_store: Optional[GraphQLiteGraphStore] = None,
    ) -> None:
        self._root = Path(root).resolve()
        self._agent_id = agent_id
        self._graph_store = graph_store
        self._sync_state_path = self._root / '.teaagent' / 'federated_sync_state.json'
        self._sync_state = self._load_sync_state()
        self._pending_changes: list[GraphChange] = []
        self._state_lock = threading.RLock()

    def _load_sync_state(self) -> SyncState:
        """Load sync state from disk."""
        if not self._sync_state_path.exists():
            return SyncState(
                agent_id=self._agent_id,
                graph_version='0',
                last_sync_time=0.0,
                sequence_number=0,
            )

        try:
            data = json.loads(self._sync_state_path.read_text(encoding='utf-8'))
            return SyncState(
                agent_id=data['agent_id'],
                graph_version=data['graph_version'],
                last_sync_time=data['last_sync_time'],
                sequence_number=data['sequence_number'],
                peer_states=data.get('peer_states', {}),
            )
        except (json.JSONDecodeError, KeyError):
            return SyncState(
                agent_id=self._agent_id,
                graph_version='0',
                last_sync_time=0.0,
                sequence_number=0,
            )

    def _save_sync_state(self) -> None:
        """Save sync state to disk (atomic write under file lock)."""
        data = {
            'agent_id': self._sync_state.agent_id,
            'graph_version': self._sync_state.graph_version,
            'last_sync_time': self._sync_state.last_sync_time,
            'sequence_number': self._sync_state.sequence_number,
            'peer_states': self._sync_state.peer_states,
        }
        payload = json.dumps(data, indent=2)
        with self._state_lock:
            atomic_write_text(self._sync_state_path, payload)

    def _generate_change_id(self, change_type: str, data: dict[str, Any]) -> str:
        """Generate unique ID for a change based on content hash."""
        content = json.dumps({'type': change_type, 'data': data}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _update_graph_version(self) -> str:
        """Update graph version based on current state."""
        # Simple version increment - in production, use content hash
        current_version = (
            int(self._sync_state.graph_version)
            if self._sync_state.graph_version.isdigit()
            else 0
        )
        new_version = str(current_version + 1)
        self._sync_state = SyncState(
            agent_id=self._sync_state.agent_id,
            graph_version=new_version,
            last_sync_time=self._sync_state.last_sync_time,
            sequence_number=self._sync_state.sequence_number,
            peer_states=self._sync_state.peer_states,
        )
        self._save_sync_state()
        return new_version

    def record_node_change(
        self,
        node_id: str,
        change_type: str,
        data: dict[str, Any],
    ) -> GraphChange:
        """Record a node change for synchronization."""
        change_id = self._generate_change_id(change_type, data)
        change = GraphChange(
            change_id=change_id,
            timestamp=time.time(),
            node_id=node_id,
            change_type=change_type,
            data=data,
            source_agent_id=self._agent_id,
        )
        with self._state_lock:
            self._pending_changes.append(change)
        return change

    def record_edge_change(
        self,
        edge_id: str,
        change_type: str,
        data: dict[str, Any],
    ) -> GraphChange:
        """Record an edge change for synchronization."""
        change_id = self._generate_change_id(change_type, data)
        change = GraphChange(
            change_id=change_id,
            timestamp=time.time(),
            edge_id=edge_id,
            change_type=change_type,
            data=data,
            source_agent_id=self._agent_id,
        )
        with self._state_lock:
            self._pending_changes.append(change)
        return change

    def create_sync_message(self) -> SyncMessage:
        """Create a sync message with pending changes."""
        with self._state_lock:
            return self._create_sync_message_locked()

    def _create_sync_message_locked(self) -> SyncMessage:
        self._sync_state = SyncState(
            agent_id=self._sync_state.agent_id,
            graph_version=self._sync_state.graph_version,
            last_sync_time=time.time(),
            sequence_number=self._sync_state.sequence_number + 1,
            peer_states=self._sync_state.peer_states,
        )
        self._save_sync_state()

        message = SyncMessage(
            message_id=hashlib.sha256(
                f'{self._agent_id}{time.time()}'.encode()
            ).hexdigest()[:16],
            sender_agent_id=self._agent_id,
            timestamp=time.time(),
            changes=list(self._pending_changes),
            sequence_number=self._sync_state.sequence_number,
            graph_version=self._sync_state.graph_version,
        )

        self._pending_changes.clear()
        return message

    def process_sync_message(self, message: SyncMessage) -> SyncAck:
        """Process incoming sync message and apply changes."""
        accepted_changes = []
        rejected_changes = []
        conflicts = []

        if not self._graph_store:
            return SyncAck(
                message_id=message.message_id,
                receiver_agent_id=self._agent_id,
                timestamp=time.time(),
                accepted_changes=[],
                rejected_changes=[c.change_id for c in message.changes],
                conflicts=['No graph store available'],
            )

        for change in message.changes:
            try:
                if self._apply_change(change):
                    accepted_changes.append(change.change_id)
                else:
                    rejected_changes.append(change.change_id)
            except (ValueError, KeyError, TypeError, OSError) as exc:
                rejected_changes.append(change.change_id)
                conflicts.append(f'{change.change_id}: {str(exc)}')
                logger.warning('Failed to apply change %s: %s', change.change_id, exc)

        # Update peer state
        self._sync_state.peer_states[message.sender_agent_id] = {
            'last_seen_sequence': message.sequence_number,
            'graph_version': message.graph_version,
            'last_seen_time': message.timestamp,
        }
        self._save_sync_state()

        # Update our graph version if we accepted changes
        if accepted_changes:
            self._update_graph_version()

        return SyncAck(
            message_id=message.message_id,
            receiver_agent_id=self._agent_id,
            timestamp=time.time(),
            accepted_changes=accepted_changes,
            rejected_changes=rejected_changes,
            conflicts=conflicts,
        )

    def _apply_change(self, change: GraphChange) -> bool:
        """Apply a single change to the graph store."""
        if change.change_type == 'node_add':
            return self._apply_node_add(change)
        elif change.change_type == 'node_update':
            return self._apply_node_update(change)
        elif change.change_type == 'node_delete':
            return self._apply_node_delete(change)
        elif change.change_type == 'edge_add':
            return self._apply_edge_add(change)
        elif change.change_type == 'edge_delete':
            return self._apply_edge_delete(change)
        return False

    def _apply_node_add(self, change: GraphChange) -> bool:
        """Apply node addition."""
        if not change.node_id:
            return False
        if self._graph_store is None:
            return False
        try:
            self._graph_store.graph.upsert_node(
                change.node_id,
                change.data,
                label=change.data.get('label', 'CodeNode'),
            )
            return True
        except (OSError, ValueError, TypeError, KeyError) as exc:
            logger.debug('Failed to apply node add %s: %s', change.node_id, exc)
            return False

    def _apply_node_update(self, change: GraphChange) -> bool:
        """Apply node update."""
        if not change.node_id:
            return False
        if self._graph_store is None:
            return False
        try:
            self._graph_store.graph.upsert_node(
                change.node_id,
                change.data,
                label=change.data.get('label', 'CodeNode'),
            )
            return True
        except (OSError, ValueError, TypeError, KeyError) as exc:
            logger.debug('Failed to apply node update %s: %s', change.node_id, exc)
            return False

    def _apply_node_delete(self, change: GraphChange) -> bool:
        """Apply node deletion."""
        if not change.node_id:
            return False
        if self._graph_store is None:
            return False
        try:
            self._graph_store.graph.delete_node(change.node_id)
            return True
        except (OSError, ValueError, TypeError, KeyError) as exc:
            logger.debug('Failed to apply node delete %s: %s', change.node_id, exc)
            return False

    def _apply_edge_add(self, change: GraphChange) -> bool:
        """Apply edge addition."""
        if not change.edge_id:
            return False
        if self._graph_store is None:
            return False
        try:
            from_id = change.data.get('from')
            to_id = change.data.get('to')
            edge_type = change.data.get('edge_type', 'RELATED')
            if from_id and to_id:
                self._graph_store.graph.upsert_edge(
                    from_id,
                    to_id,
                    edge_type,
                    change.data,
                )
                return True
        except (OSError, ValueError, TypeError, KeyError) as exc:
            logger.debug('Failed to apply edge add %s: %s', change.edge_id, exc)
            return False
        return False

    def _apply_edge_delete(self, change: GraphChange) -> bool:
        """Apply edge deletion."""
        if not change.edge_id:
            return False
        if self._graph_store is None:
            return False
        try:
            from_id = change.data.get('from')
            to_id = change.data.get('to')
            edge_type = change.data.get('edge_type', 'RELATED')
            if from_id and to_id:
                self._graph_store.graph.delete_edge(from_id, to_id, edge_type)
                return True
        except (OSError, ValueError, TypeError, KeyError) as exc:
            logger.debug('Failed to apply edge delete %s: %s', change.edge_id, exc)
            return False
        return False

    def get_sync_state(self) -> SyncState:
        """Get current sync state."""
        return self._sync_state

    def export_sync_message(self, message: SyncMessage, path: str | Path) -> None:
        """Export sync message to file for webhook/P2P transfer."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'message_id': message.message_id,
            'sender_agent_id': message.sender_agent_id,
            'timestamp': message.timestamp,
            'sequence_number': message.sequence_number,
            'graph_version': message.graph_version,
            'changes': [
                {
                    'change_id': c.change_id,
                    'timestamp': c.timestamp,
                    'node_id': c.node_id,
                    'edge_id': c.edge_id,
                    'change_type': c.change_type,
                    'data': c.data,
                    'source_agent_id': c.source_agent_id,
                }
                for c in message.changes
            ],
        }
        path.write_text(json.dumps(data, indent=2), encoding='utf-8')

    def import_sync_message(self, path: str | Path) -> Optional[SyncMessage]:
        """Import sync message from file."""
        path = Path(path)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            changes = [
                GraphChange(
                    change_id=c['change_id'],
                    timestamp=c['timestamp'],
                    node_id=c.get('node_id'),
                    edge_id=c.get('edge_id'),
                    change_type=c['change_type'],
                    data=c['data'],
                    source_agent_id=c['source_agent_id'],
                )
                for c in data['changes']
            ]
            return SyncMessage(
                message_id=data['message_id'],
                sender_agent_id=data['sender_agent_id'],
                timestamp=data['timestamp'],
                changes=changes,
                sequence_number=data['sequence_number'],
                graph_version=data['graph_version'],
            )
        except (json.JSONDecodeError, KeyError, OSError):
            logger.warning('Failed to import sync message from %s', path)
            return None

    @staticmethod
    def _validate_relay_url(url: str) -> str:
        """Validate a relay URL for SSRF safety.

        Ensures the URL uses a safe scheme (https, or http for loopback)
        and does not point to private IP ranges (except loopback).

        Returns the validated URL.

        Raises:
            ValueError: If the URL fails validation.
        """
        import ipaddress

        parsed = urlparse(url)

        if parsed.scheme not in ('http', 'https'):
            raise ValueError(
                f"Unsupported URL scheme: {parsed.scheme!r} "
                '(only http/https allowed)'
            )

        host = parsed.hostname or ''
        if not host:
            raise ValueError('URL has no hostname')

        # Resolve hostname to IP addresses to block wildcard DNS SSRF
        try:
            addr = ipaddress.ip_address(host)
            # host is a literal IP address
            if addr.is_private and not addr.is_loopback:
                raise ValueError(
                    f'URL points to private IP range: {host}'
                )
            return url  # literal IP is valid (loopback or public)
        except ValueError:
            pass  # host is not a literal IP — resolve it below

        # Resolve hostname to actual IP addresses
        try:
            ips = socket.getaddrinfo(host, 80)
            resolved_ips = {ip[4][0] for ip in ips}
        except socket.gaierror as exc:
            raise ValueError(f"Failed to resolve host '{host}': {exc}") from exc

        for ip_str in resolved_ips:
            addr = ipaddress.ip_address(ip_str)
            if addr.is_private and not addr.is_loopback:
                raise ValueError(
                    f"URL host '{host}' resolves to private IP range: {ip_str}"
                )

        # Bake resolved IP into URL to prevent DNS rebinding TOCTOU
        # The actual HTTP connection uses this IP, not re-resolving the hostname.
        resolved_host = sorted(resolved_ips)[0]
        new_netloc = (
            f"{resolved_host}:{parsed.port}" if parsed.port else str(resolved_host)
        )
        safe_url = parsed._replace(netloc=new_netloc).geturl()
        return safe_url

    def broadcast_approval_request(
        self,
        request: ApprovalRequestMessage,
        peer_agent_ids: list[str],
        *,
        peer_relay_urls: dict[str, str] | None = None,
        relay_api_token: str | None = None,
    ) -> dict[str, bool]:
        """Broadcast approval request via HTTP relay and/or local file drop.

        When ``peer_relay_urls`` maps peer IDs to relay base URLs, POSTs the
        request to each peer's ``/api/v1/approval-requests``. Local file broadcast
        is always attempted for dev/offline peers.
        """
        from dataclasses import asdict

        from teaagent.signature_relay import SignatureRelayClient

        results: dict[str, bool] = {}
        relay_urls = peer_relay_urls or {}
        token = (
            relay_api_token
            if relay_api_token is not None
            else signature_relay_api_token()
        )
        http_client = SignatureRelayClient(api_token=token) if relay_urls else None

        for peer_id in peer_agent_ids:
            http_ok = False
            if http_client is not None and peer_id in relay_urls:
                try:
                    safe_url = self._validate_relay_url(relay_urls[peer_id])
                except ValueError as exc:
                    logger.warning(
                        'Invalid relay URL for peer %s: %s', peer_id, exc
                    )
                else:
                    payload = asdict(request)
                    payload['target_peer_id'] = peer_id
                    result = http_client.post_approval_request(safe_url, payload)
                    http_ok = bool(result.get('ok'))
                    if not http_ok:
                        logger.warning(
                            'HTTP approval broadcast to %s failed: %s',
                            peer_id,
                            result.get('error'),
                        )
            file_ok = False
            try:
                broadcast_path = (
                    self._root
                    / '.teaagent'
                    / 'pending_approvals'
                    / f'{request.request_id}_{peer_id}.json'
                )
                broadcast_path.parent.mkdir(parents=True, exist_ok=True)
                data = {
                    'request_id': request.request_id,
                    'tool_name': request.tool_name,
                    'call_id': request.call_id,
                    'arguments': request.arguments,
                    'request_hash': request.request_hash,
                    'timestamp': request.timestamp,
                    'requester_agent_id': request.requester_agent_id,
                    'required_approvals': request.required_approvals,
                    'timeout_seconds': request.timeout_seconds,
                    'target_peer_id': peer_id,
                    'signature_submit_url': request.signature_submit_url,
                }
                broadcast_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
                file_ok = True
            except OSError as exc:
                logger.warning('Failed to broadcast approval to %s: %s', peer_id, exc)
            results[peer_id] = http_ok or file_ok

        return results

    async def collect_approval_signatures(
        self,
        request_id: str,
        timeout_seconds: int,
        *,
        required_approvals: int = 1,
        relay_base_url: str | None = None,
        relay_api_token: str | None = None,
    ) -> list[ApprovalSignatureMessage]:
        """Collect approval signatures from peers for a request asynchronously.

        Args:
            request_id: The approval request ID to collect signatures for.
            timeout_seconds: Maximum time to wait for signatures.
            required_approvals: Minimum number of peer approvals needed.
                Collection short-circuits once this threshold is reached.

        Returns:
            List of signature messages received from peers.
        """
        import asyncio

        signatures: list[ApprovalSignatureMessage] = []
        seen_peers: set[str] = set()
        approvals_dir = self._root / '.teaagent' / 'pending_approvals'

        # Poll for incoming signature files using async sleep
        poll_interval = 0.1
        max_polls = max(1, int(timeout_seconds / poll_interval))
        polls = 0

        loop = asyncio.get_running_loop()
        http_client = None
        relay_url = relay_base_url
        if relay_url:
            from teaagent.signature_relay import SignatureRelayClient

            token = (
                relay_api_token
                if relay_api_token is not None
                else signature_relay_api_token()
            )
            http_client = SignatureRelayClient(api_token=token)

        while polls < max_polls:
            if http_client is not None and relay_url is not None:
                remote_items = await loop.run_in_executor(
                    None,
                    functools.partial(
                        http_client.fetch_signatures, relay_url, request_id
                    ),
                )
                for data in remote_items:
                    try:
                        expected_token = federated_signature_token()
                        if (
                            expected_token is not None
                            and data.get('auth_token') != expected_token
                        ):
                            continue
                        peer_id = str(data['peer_id'])
                        if peer_id in seen_peers:
                            continue
                        sig_msg = ApprovalSignatureMessage(
                            request_id=str(data['request_id']),
                            peer_id=peer_id,
                            signature=str(data['signature']),
                            ssh_key_id=data.get('ssh_key_id'),
                            timestamp=float(data.get('timestamp', time.time())),
                        )
                        seen_peers.add(peer_id)
                        signatures.append(sig_msg)
                    except (KeyError, TypeError, ValueError):
                        continue

            sig_files: list[Path] = []
            if approvals_dir.exists():
                sig_files = await loop.run_in_executor(
                    None,
                    lambda: list(approvals_dir.glob(f'{request_id}_signature_*.json')),
                )

            for sig_file in sig_files:
                try:
                    content = await loop.run_in_executor(
                        None,
                        functools.partial(sig_file.read_text, encoding='utf-8'),
                    )
                    data = json.loads(content)
                    expected_token = federated_signature_token()
                    if (
                        expected_token is not None
                        and data.get('auth_token') != expected_token
                    ):
                        continue
                    peer_id = data['peer_id']
                    if peer_id in seen_peers:
                        continue
                    sig_msg = ApprovalSignatureMessage(
                        request_id=data['request_id'],
                        peer_id=peer_id,
                        signature=data['signature'],
                        ssh_key_id=data.get('ssh_key_id'),
                        timestamp=data.get('timestamp', time.time()),
                    )
                    with contextlib.suppress(OSError):
                        await loop.run_in_executor(None, sig_file.unlink)
                    seen_peers.add(peer_id)
                    signatures.append(sig_msg)
                except (json.JSONDecodeError, KeyError, OSError):
                    continue

            if len(signatures) >= required_approvals:
                break

            await asyncio.sleep(poll_interval)
            polls += 1

        return signatures

    def submit_approval_signature(
        self,
        request_id: str,
        peer_id: str,
        signature: str,
        ssh_key_id: Optional[str] = None,
    ) -> bool:
        """Submit an approval signature for a request.

        Args:
            request_id: The approval request ID.
            peer_id: The peer agent ID submitting the signature.
            signature: The cryptographic signature.
            ssh_key_id: Optional SSH key identifier.

        Returns:
            True if signature was successfully submitted.
        """
        try:
            sig_path = (
                self._root
                / '.teaagent'
                / 'pending_approvals'
                / f'{request_id}_signature_{peer_id}.json'
            )
            sig_path.parent.mkdir(parents=True, exist_ok=True)

            data: dict[str, Any] = {
                'request_id': request_id,
                'peer_id': peer_id,
                'signature': signature,
                'ssh_key_id': ssh_key_id,
                'timestamp': time.time(),
            }
            token = federated_signature_token()
            if token is not None:
                data['auth_token'] = token

            sig_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
            return True
        except OSError as exc:
            logger.warning('Failed to submit approval signature: %s', exc)
            return False
