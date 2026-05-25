"""Skills Marketplace / Community Hub — publish, search, install skills.

Features:
- ``MarketplaceRegistry`` — local index of published skill candidates
- ``MarketplaceClient`` — fetch remote registry (agentskills.io compatible)
- ``skill publish`` — publish a local SKILL.md to the registry
- ``skill search`` — search available skills
- ``skill install from-marketplace`` — install from registry
"""

from teaagent.marketplace._client import (
    MarketplaceClient,
    RemoteSkillEntry,
)
from teaagent.marketplace._registry import (
    MarketplaceEntry,
    MarketplaceRegistry,
)

__all__ = [
    'MarketplaceEntry',
    'MarketplaceRegistry',
    'MarketplaceClient',
    'RemoteSkillEntry',
]
