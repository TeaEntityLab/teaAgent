"""TASK-005 verify-first: harden trust boundaries for extensions and MCP.

Acceptance criterion (roadmap-work-items-2026-06-04, TASK-005):
"no expired trust entry continues to act trusted; unsafe extension paths are
explicit."

Existing tests cover the ``is_server_trust_expired`` predicate. These tests pin
the *enforcement* at call time, which is the actual trust-boundary guarantee:

- ``merged_tool_filters`` drops an expired server's tools entirely;
- the registered pre-tool hook raises an explicit ``HookError`` (naming the
  server) when an expired server's tool is invoked.
"""

from __future__ import annotations

import os
import tempfile
import time

import pytest
from cryptography.fernet import Fernet

from teaagent.hooks import HookError
from teaagent.mcp_trust import (
    MCPServerTrust,
    MCPTrustPolicy,
    apply_mcp_trust_hooks,
    merged_tool_filters,
    save_mcp_trust_policy,
)
from teaagent.types import ToolAnnotations, ToolRegistry

_EXPIRED = time.time() - 3600
_ACTIVE = time.time() + 3600


def test_expired_server_grants_no_tools():
    policy = MCPTrustPolicy()
    policy.servers['srv'] = MCPServerTrust(
        trusted=True, allowed_tools=['srv_tool'], expires_at=_EXPIRED
    )
    allowed, _denied = merged_tool_filters(policy)
    assert 'srv_tool' not in allowed


def test_active_server_grants_its_tools():
    policy = MCPTrustPolicy()
    policy.servers['srv'] = MCPServerTrust(
        trusted=True, allowed_tools=['srv_tool'], expires_at=_ACTIVE
    )
    allowed, _denied = merged_tool_filters(policy)
    assert 'srv_tool' in allowed


@pytest.fixture
def mcp_trust_setup():
    prev_key = os.environ.get('TEAAGENT_MCP_TRUST_KEY')
    os.environ['TEAAGENT_MCP_TRUST_KEY'] = Fernet.generate_key().decode()
    tmp = tempfile.mkdtemp()
    yield tmp, prev_key
    if prev_key is None:
        os.environ.pop('TEAAGENT_MCP_TRUST_KEY', None)
    else:
        os.environ['TEAAGENT_MCP_TRUST_KEY'] = prev_key
    # Verify cleanup
    import shutil

    assert os.path.exists(tmp), (
        f'Temporary directory {tmp} should still exist before cleanup'
    )
    shutil.rmtree(tmp)
    assert not os.path.exists(tmp), f'Temporary directory {tmp} was not cleaned up'


def _registry_for(tmp: str, server: MCPServerTrust) -> ToolRegistry:
    policy = MCPTrustPolicy()
    policy.servers['srv'] = server
    save_mcp_trust_policy(tmp, policy)
    registry = ToolRegistry()
    registry.register(
        name='srv_tool',
        description='remote MCP test tool',
        input_schema={'type': 'object', 'properties': {}},
        output_schema={'type': 'object', 'properties': {}},
        annotations=ToolAnnotations(read_only=True),
        handler=lambda args: {},
        mcp_server_name='srv',
    )
    apply_mcp_trust_hooks(registry, tmp)
    return registry


def test_expired_server_tool_is_blocked_at_call_time(mcp_trust_setup):
    tmp, _prev_key = mcp_trust_setup
    registry = _registry_for(
        tmp,
        MCPServerTrust(trusted=True, allowed_tools=['srv_tool'], expires_at=_EXPIRED),
    )
    with pytest.raises(HookError) as ctx:
        registry.hook_registry.run_pre_hooks('srv_tool', {})
    # Unsafe path is explicit: the error names the server and the cause.
    assert 'expired' in str(ctx.value).lower()
    assert 'srv' in str(ctx.value)


def test_active_server_tool_is_allowed_at_call_time(mcp_trust_setup):
    tmp, _prev_key = mcp_trust_setup
    registry = _registry_for(
        tmp,
        MCPServerTrust(trusted=True, allowed_tools=['srv_tool'], expires_at=_ACTIVE),
    )
    # Should not raise.
    registry.hook_registry.run_pre_hooks('srv_tool', {})
