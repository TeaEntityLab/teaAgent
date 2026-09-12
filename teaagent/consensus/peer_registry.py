"""Peer registry for the consensus system."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from teaagent.consensus.types import PeerIdentity

logger = logging.getLogger(__name__)


class PeerRegistry:
    """Registry for managing peer identities."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        """Initialize peer registry.

        Args:
            storage_path: Path to persist peer registry. If None, uses in-memory storage.
        """
        self.storage_path = storage_path
        self._peers: Dict[str, PeerIdentity] = {}
        if storage_path:
            self._load()

    def register(self, peer: PeerIdentity) -> None:
        """Register a new peer.

        Args:
            peer: The peer identity to register

        Raises:
            ValueError: If a peer with the same name already exists
        """
        if peer.name in self._peers:
            raise ValueError(f"Peer '{peer.name}' already registered")
        self._peers[peer.name] = peer
        if self.storage_path:
            self._save()

    def unregister(self, peer_name: str) -> Optional[PeerIdentity]:
        """Unregister a peer.

        Args:
            peer_name: Name of the peer to unregister

        Returns:
            The unregistered peer, or None if not found
        """
        peer = self._peers.pop(peer_name, None)
        if peer and self.storage_path:
            self._save()
        return peer

    def get(self, peer_name: str) -> Optional[PeerIdentity]:
        """Get a peer by name.

        Args:
            peer_name: Name of the peer

        Returns:
            The peer identity, or None if not found
        """
        return self._peers.get(peer_name)

    def list_all(self) -> List[PeerIdentity]:
        """List all registered peers.

        Returns:
            List of all peer identities
        """
        return list(self._peers.values())

    def list_active(self) -> List[PeerIdentity]:
        """List only active peers.

        Returns:
            List of active peer identities
        """
        return [peer for peer in self._peers.values() if peer.is_active]

    def activate(self, peer_name: str) -> bool:
        """Activate a peer.

        Args:
            peer_name: Name of the peer to activate

        Returns:
            True if peer was activated, False if not found
        """
        peer = self._peers.get(peer_name)
        if peer:
            active_peer = PeerIdentity(
                name=peer.name,
                ssh_public_key=peer.ssh_public_key,
                created_at=peer.created_at,
                is_active=True,
            )
            self._peers[peer_name] = active_peer
            if self.storage_path:
                self._save()
            return True
        return False

    def deactivate(self, peer_name: str) -> bool:
        """Deactivate a peer.

        Args:
            peer_name: Name of the peer to deactivate

        Returns:
            True if peer was deactivated, False if not found
        """
        peer = self._peers.get(peer_name)
        if peer:
            inactive_peer = PeerIdentity(
                name=peer.name,
                ssh_public_key=peer.ssh_public_key,
                created_at=peer.created_at,
                is_active=False,
            )
            self._peers[peer_name] = inactive_peer
            if self.storage_path:
                self._save()
            return True
        return False

    def rotate_key(self, peer_name: str, new_ssh_key: str) -> bool:
        """Rotate SSH key for a peer.

        Args:
            peer_name: Name of the peer
            new_ssh_key: New SSH public key

        Returns:
            True if key was rotated, False if peer not found
        """
        peer = self._peers.get(peer_name)
        if peer:
            updated_peer = PeerIdentity(
                name=peer.name,
                ssh_public_key=new_ssh_key,
                created_at=peer.created_at,
                is_active=peer.is_active,
            )
            self._peers[peer_name] = updated_peer
            if self.storage_path:
                self._save()
            return True
        return False

    def verify_peer(self, peer_name: str, message: str, signature: str) -> bool:
        """Verify a signature from a peer.

        Args:
            peer_name: Name of the peer
            message: The message that was signed
            signature: The signature to verify

        Returns:
            True if signature is valid from this peer, False otherwise
        """
        peer = self.get(peer_name)
        if not peer or not peer.is_active:
            return False
        return peer.verify_signature(message, signature)

    def _save(self) -> None:
        """Save peer registry to storage."""
        if not self.storage_path:
            return

        data = {
            'peers': [
                {
                    'name': peer.name,
                    'ssh_public_key': peer.ssh_public_key,
                    'created_at': peer.created_at.isoformat(),
                    'is_active': peer.is_active,
                }
                for peer in self._peers.values()
            ]
        }

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(data, indent=2), encoding='utf-8')

    def _load(self) -> None:
        """Load peer registry from storage."""
        if not self.storage_path or not self.storage_path.exists():
            return

        try:
            data = json.loads(self.storage_path.read_text(encoding='utf-8'))
            for peer_data in data.get('peers', []):
                peer = PeerIdentity(
                    name=peer_data['name'],
                    ssh_public_key=peer_data['ssh_public_key'],
                    created_at=datetime.fromisoformat(peer_data['created_at'])
                    if 'created_at' in peer_data
                    else datetime.now(timezone.utc),
                    is_active=peer_data.get('is_active', True),
                )
                self._peers[peer.name] = peer
        except (json.JSONDecodeError, OSError, KeyError, ValueError, TypeError) as exc:
            logger.warning('Failed to load peer registry: %s', exc)
            self._peers = {}
