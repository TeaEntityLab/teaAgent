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
import unittest

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


class MergedFilterExpiryTests(unittest.TestCase):
    def test_expired_server_grants_no_tools(self) -> None:
        policy = MCPTrustPolicy()
        policy.servers['srv'] = MCPServerTrust(
            trusted=True, allowed_tools=['srv_tool'], expires_at=_EXPIRED
        )
        allowed, _denied = merged_tool_filters(policy)
        self.assertNotIn('srv_tool', allowed)

    def test_active_server_grants_its_tools(self) -> None:
        policy = MCPTrustPolicy()
        policy.servers['srv'] = MCPServerTrust(
            trusted=True, allowed_tools=['srv_tool'], expires_at=_ACTIVE
        )
        allowed, _denied = merged_tool_filters(policy)
        self.assertIn('srv_tool', allowed)


class CallTimeHookEnforcementTests(unittest.TestCase):
    def setUp(self) -> None:
        self._prev_key = os.environ.get('TEAAGENT_MCP_TRUST_KEY')
        os.environ['TEAAGENT_MCP_TRUST_KEY'] = Fernet.generate_key().decode()
        self._tmp = tempfile.mkdtemp()

    def tearDown(self) -> None:
        if self._prev_key is None:
            os.environ.pop('TEAAGENT_MCP_TRUST_KEY', None)
        else:
            os.environ['TEAAGENT_MCP_TRUST_KEY'] = self._prev_key

    def _registry_for(self, server: MCPServerTrust) -> ToolRegistry:
        policy = MCPTrustPolicy()
        policy.servers['srv'] = server
        save_mcp_trust_policy(self._tmp, policy)
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
        apply_mcp_trust_hooks(registry, self._tmp)
        return registry

    def test_expired_server_tool_is_blocked_at_call_time(self) -> None:
        registry = self._registry_for(
            MCPServerTrust(
                trusted=True, allowed_tools=['srv_tool'], expires_at=_EXPIRED
            )
        )
        with self.assertRaises(HookError) as ctx:
            registry.hook_registry.run_pre_hooks('srv_tool', {})
        # Unsafe path is explicit: the error names the server and the cause.
        self.assertIn('expired', str(ctx.exception).lower())
        self.assertIn('srv', str(ctx.exception))

    def test_active_server_tool_is_allowed_at_call_time(self) -> None:
        registry = self._registry_for(
            MCPServerTrust(trusted=True, allowed_tools=['srv_tool'], expires_at=_ACTIVE)
        )
        # Should not raise.
        registry.hook_registry.run_pre_hooks('srv_tool', {})


if __name__ == '__main__':
    unittest.main()
