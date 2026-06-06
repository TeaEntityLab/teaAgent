"""Environment-gated security posture flags for local HTTP surfaces and signatures."""

from __future__ import annotations

import os


def allow_dev_signatures() -> bool:
    """Allow dev-hash signatures (never for production WAN surfaces)."""
    return _env_truthy('TEAAGENT_ALLOW_DEV_SIGNATURES')


def strict_local_services() -> bool:
    """Require bearer/OAuth on loopback MCP HTTP when set."""
    return _env_truthy('TEAAGENT_STRICT_LOCAL')


def plugins_strict_audit() -> bool:
    """Fail closed on unverified plugin entry points when set."""
    return _env_truthy('TEAAGENT_PLUGINS_STRICT')


def compliance_mode() -> bool:
    """Fail closed on audit durability errors when set (WS3-001)."""
    return _env_truthy('TEAAGENT_COMPLIANCE_MODE')


def audit_chain_strict() -> bool:
    """Reject legacy audit chain resets unless legacy compat is enabled (WS3-002)."""
    return _env_truthy('TEAAGENT_AUDIT_CHAIN_STRICT')


def audit_chain_legacy_compat() -> bool:
    """Allow legacy audit lines without chain fields when strict mode is on."""
    return _env_truthy('TEAAGENT_AUDIT_CHAIN_LEGACY_COMPAT', default=True)


def _env_truthy(name: str, *, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {'1', 'true', 'yes', 'on'}


def signature_relay_api_token() -> str | None:
    """Bearer token for signature relay HTTP client (WAN multi-sig)."""
    for name in ('TEAAGENT_SIGNATURE_RELAY_TOKEN', 'TEAAGENT_RELAY_TOKEN'):
        value = os.environ.get(name, '').strip()
        if value:
            return value
    return None


def federated_signature_token() -> str | None:
    """Optional shared secret for file-based P2P approval signature files.

    When set, ``submit_approval_signature`` embeds the token and
    ``collect_approval_signatures`` ignores files with a missing or wrong token.
    """
    value = os.environ.get('TEAAGENT_FEDERATED_SIGNATURE_TOKEN', '').strip()
    return value or None
