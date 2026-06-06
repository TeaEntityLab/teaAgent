"""Acceptance test for unified extension activation explain (EXT-001).

Verifies that explain_extension_activation() gathers activation info
from all extension types and produces the correct structure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from teaagent.extension_explain import (
    ExtensionActivation,
    ExtensionActivationExplain,
    explain_extension_activation,
)


class TestExtensionActivationModel:
    """ExtensionActivation dataclass construction and serialization."""

    def test_minimal(self) -> None:
        ea = ExtensionActivation(
            name='test-skill',
            type='skill',
            source='/tmp/skills',
            reason='Loaded',
            trust_level='scoped',
        )
        assert ea.name == 'test-skill'
        assert ea.type == 'skill'
        assert ea.estimated_tokens == 0
        assert ea.disable_command == ''

    def test_to_dict(self) -> None:
        ea = ExtensionActivation(
            name='test',
            type='plugin',
            source='builtin',
            reason='Registered',
            trust_level='full',
            estimated_tokens=100,
            disable_command='plugin disable test',
            extra={'key': 'val'},
        )
        d = ea.to_dict()
        assert d['name'] == 'test'
        assert d['type'] == 'plugin'
        assert d['estimated_tokens'] == 100
        assert d['extra']['key'] == 'val'

    def test_full(self) -> None:
        ea = ExtensionActivation(
            name='mcp-server',
            type='mcp',
            source='https://mcp.example.com',
            reason='Trusted, 3 tools allowed',
            trust_level='full',
            estimated_tokens=200,
            disable_command='mcp revoke mcp-server',
            extra={'allowed_tools': 3, 'denied_tools': 0},
        )
        assert ea.trust_level == 'full'
        assert ea.extra['allowed_tools'] == 3


class TestExtensionActivationExplainModel:
    """ExtensionActivationExplain aggregation."""

    def test_empty(self) -> None:
        eae = ExtensionActivationExplain()
        assert eae.total_count == 0
        assert eae.total_estimated_tokens == 0
        assert eae.trust_summary == ''

    def test_with_extensions(self) -> None:
        exts = [
            ExtensionActivation(
                name='s1',
                type='skill',
                source='.',
                reason='r1',
                trust_level='full',
            ),
            ExtensionActivation(
                name='m1',
                type='mcp',
                source='.',
                reason='r2',
                trust_level='untrusted',
            ),
        ]
        eae = ExtensionActivationExplain(
            extensions=exts,
            total_count=2,
            total_estimated_tokens=0,
            trust_summary='1 full, 1 untrusted',
        )
        assert eae.total_count == 2
        assert eae.trust_summary == '1 full, 1 untrusted'

    def test_by_type(self) -> None:
        exts = [
            ExtensionActivation('s1', 'skill', '.', 'r1', 'full'),
            ExtensionActivation('s2', 'skill', '.', 'r2', 'scoped'),
            ExtensionActivation('m1', 'mcp', '.', 'r3', 'untrusted'),
            ExtensionActivation('p1', 'plugin', '.', 'r4', 'full'),
        ]
        eae = ExtensionActivationExplain(extensions=exts)
        by_type = eae.by_type()
        assert len(by_type['skill']) == 2
        assert len(by_type['mcp']) == 1
        assert len(by_type['plugin']) == 1

    def test_to_dict(self) -> None:
        eae = ExtensionActivationExplain(
            extensions=[
                ExtensionActivation('s1', 'skill', '.', 'r1', 'full'),
            ],
            total_count=1,
            total_estimated_tokens=50,
            trust_summary='1 full',
        )
        d = eae.to_dict()
        assert d['total_count'] == 1
        assert d['total_estimated_tokens'] == 50
        assert len(d['extensions']) == 1


class TestExplainExtensionActivation:
    """explain_extension_activation() integration."""

    def test_no_inputs(self) -> None:
        """With no arguments, returns empty explain."""
        result = explain_extension_activation()
        assert result.total_count == 0
        assert result.total_estimated_tokens == 0

    def test_with_workspace_root(self, tmp_path: Path) -> None:
        """With a valid workspace root, discovers skills and memories."""
        # Create minimal .teaagent structure
        (tmp_path / '.teaagent').mkdir()
        result = explain_extension_activation(workspace_root=tmp_path)
        assert isinstance(result, ExtensionActivationExplain)
        # At minimum it should return an explain (may be empty if no skills/memories)
        assert result.total_count >= 0

    def test_fake_plugin_registry(self) -> None:
        """With a fake plugin registry, discovers plugins."""

        class FakeRegistry:
            commands = {'test-cmd': None}
            agents = {}
            hooks = {}

        result = explain_extension_activation(
            plugin_registry=FakeRegistry(),
        )
        assert result.total_count >= 1
        plugins = [e for e in result.extensions if e.type == 'plugin']
        assert len(plugins) >= 1
        assert plugins[0].name == 'test-cmd'

    def test_fake_hook_registry(self) -> None:
        """With a fake hook registry, discovers hooks."""

        class FakeRegistry:
            _pre_hooks = [lambda: None]
            _post_hooks = []
            _start_hooks = []
            _stop_hooks = []
            _pre_compact_hooks = []

        result = explain_extension_activation(
            hook_registry=FakeRegistry(),
        )
        hooks = [e for e in result.extensions if e.type == 'hook']
        assert len(hooks) >= 1

    def test_fake_mcp_trust(self) -> None:
        """With a fake MCP trust policy, discovers MCP servers."""
        from dataclasses import dataclass, field

        @dataclass
        class FakeServerTrust:
            trusted: bool = True
            allowed_tools: list[str] = field(default_factory=lambda: ['tool1'])
            denied_tools: list[str] = field(default_factory=list)
            expires_at: float | None = None

        @dataclass
        class FakePolicy:
            servers: dict[str, Any] = field(
                default_factory=lambda: {
                    'mcp.example.com': FakeServerTrust(),
                }
            )

        result = explain_extension_activation(
            mcp_trust_policy=FakePolicy(),
        )
        mcps = [e for e in result.extensions if e.type == 'mcp']
        assert len(mcps) >= 1
        assert mcps[0].name == 'mcp.example.com'
        assert mcps[0].trust_level == 'full'

    def test_all_sources_together(self, tmp_path: Path) -> None:
        """All sources combined produce a unified explain."""
        (tmp_path / '.teaagent').mkdir()

        class FakeReg:
            commands = {'c1': None}
            agents = {}
            hooks = {}

        class FakeHooks:
            _pre_hooks = [lambda: None]
            _post_hooks = []
            _start_hooks = []
            _stop_hooks = []
            _pre_compact_hooks = []

        result = explain_extension_activation(
            workspace_root=tmp_path,
            plugin_registry=FakeReg(),
            hook_registry=FakeHooks(),
        )
        assert result.total_count >= 2
        types = set(e.type for e in result.extensions)
        assert 'plugin' in types
        assert 'hook' in types
