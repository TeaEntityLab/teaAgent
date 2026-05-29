"""Environment-gated security posture flags for local HTTP surfaces and signatures."""

from __future__ import annotations

import os


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, '').strip().lower() in {'1', 'true', 'yes', 'on'}


def allow_dev_signatures() -> bool:
    """Allow dev-hash signatures (never for production WAN surfaces)."""
    return _env_truthy('TEAAGENT_ALLOW_DEV_SIGNATURES')


def strict_local_services() -> bool:
    """Require bearer/OAuth on loopback MCP HTTP when set."""
    return _env_truthy('TEAAGENT_STRICT_LOCAL')


def plugins_strict_audit() -> bool:
    """Fail closed on unverified plugin entry points when set."""
    return _env_truthy('TEAAGENT_PLUGINS_STRICT')


def federated_signature_token() -> str | None:
    """Optional shared secret for file-based P2P approval signature files.

    When set, ``submit_approval_signature`` embeds the token and
    ``collect_approval_signatures`` ignores files with a missing or wrong token.
    """
    value = os.environ.get('TEAAGENT_FEDERATED_SIGNATURE_TOKEN', '').strip()
    return value or None
