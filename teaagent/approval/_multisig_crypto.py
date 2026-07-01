"""Canonical multi-signature approval crypto helpers.

Single source of truth for the approval-request hash and the dev-signature
loopback guard, shared by :class:`~teaagent.policy.ApprovalPolicy` and
:class:`~teaagent.approval.manager.ApprovalManager`.

Consolidating these here removes the duplicated-hash hazard flagged by the risk
register (SEC-09): the hash was previously implemented in two files that drifted
apart, leaving one copy with a replayable 1-hour time bucket. This module is a
stdlib-only leaf (plus :mod:`teaagent.errors`, itself a leaf) so both callers can
import it without a cycle.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from teaagent.errors import ConfigError

if TYPE_CHECKING:
    from teaagent.approval.manager import MultiSigQuorumConfig

# Hosts that keep a signature relay on the local machine. Dev-hash signatures
# (which bypass real SSH verification) are only ever acceptable on these.
_LOOPBACK_HOSTNAMES = frozenset({'127.0.0.1', 'localhost', '::1'})


def generate_approval_hash(
    tool_name: str,
    call_id: str,
    arguments: dict[str, Any] | None,
    *,
    request_id: str = '',
    run_id: str = '',
) -> str:
    """Deterministic SHA-256 over an approval request's identity.

    Binds the unique per-request ``request_id`` so a captured peer signature
    cannot be replayed onto a *different* request (SEC-09). No wall-clock time
    bucket is included: ``request_id`` already guarantees per-request
    uniqueness, and a time bucket would additionally break verification when
    signature collection spans the bucket boundary (the collection timeout is
    itself measured in minutes).

    Callers that omit ``request_id`` (e.g. determinism self-checks) get a stable
    hash keyed only on the tool call identity.
    """
    content = json.dumps(
        {
            'tool_name': tool_name,
            'call_id': call_id,
            'arguments': arguments or {},
            'run_id': run_id,
            'request_id': request_id,
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()


def _relay_is_non_loopback(url: str | None) -> bool:
    """True when ``url`` names a host that is not loopback."""
    if not url:
        return False
    host = (urlparse(url).hostname or '').strip().lower()
    if not host:
        return False
    return host not in _LOOPBACK_HOSTNAMES


def non_loopback_relay_urls(config: MultiSigQuorumConfig) -> list[str]:
    """Return the relay URLs in ``config`` whose host is not loopback."""
    candidates: list[str] = []
    if config.local_relay_base_url:
        candidates.append(config.local_relay_base_url)
    candidates.extend(config.peer_relay_urls.values())
    return sorted({u for u in candidates if _relay_is_non_loopback(u)})


def resolve_allow_dev_signatures(
    config: MultiSigQuorumConfig, *, env_enabled: bool
) -> bool:
    """Decide whether dev-hash signatures may be honored, failing closed on WAN.

    Dev-hash signatures are ``sha256(message + pubkey)`` — they bypass real SSH
    verification and are only safe on loopback. When dev signatures are requested
    (via ``config.allow_dev_signatures`` or ``TEAAGENT_ALLOW_DEV_SIGNATURES``)
    while any configured signature relay points at a non-loopback host, this
    raises :class:`~teaagent.errors.ConfigError` instead of accepting forgeable
    signatures over the network (SEC-15).

    Returns ``True`` only when dev signatures are requested *and* every relay is
    loopback (or none is configured); ``False`` when they are not requested.
    """
    requested = bool(getattr(config, 'allow_dev_signatures', False)) or bool(
        env_enabled
    )
    if not requested:
        return False
    wan_relays = non_loopback_relay_urls(config)
    if wan_relays:
        raise ConfigError(
            'Dev-hash signatures cannot be honored with a non-loopback signature '
            f'relay ({", ".join(wan_relays)}). Dev signatures bypass SSH '
            'verification and are loopback-only.',
            hint=(
                'Unset TEAAGENT_ALLOW_DEV_SIGNATURES and '
                'multi_sig.allow_dev_signatures, or bind the relay to a loopback '
                'host and supply real peer_public_keys.'
            ),
        )
    return True
