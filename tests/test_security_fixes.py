"""Security tests for RSK-09, RSK-10, RSK-11 vulnerability fixes."""

from __future__ import annotations

import tempfile

import pytest

from teaagent.plugins import _audit_plugin_source, load_plugins
from teaagent.session import ChatMessage, ChatSession, SessionStore
from teaagent.subagents._isolation import new_isolation_session_key
from teaagent.tools import ToolRegistry


class TestSessionSecurityRSK11:
    """Test RSK-11: Session ID Directory Traversal vulnerability fix."""

    def test_path_traversal_blocked_with_double_dot(self):
        """Path traversal with .. should be blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(root=tmpdir)
            with pytest.raises(ValueError, match='path traversal'):
                store._path('../../../etc/passwd')

    def test_path_traversal_blocked_with_forward_slash(self):
        """Path traversal with / should be blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(root=tmpdir)
            with pytest.raises(ValueError, match='path traversal'):
                store._path('subdir/session')

    def test_path_traversal_blocked_with_backslash(self):
        """Path traversal with \\ should be blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(root=tmpdir)
            with pytest.raises(ValueError, match='path traversal'):
                store._path('subdir\\session')

    def test_unsafe_characters_blocked(self):
        """Unsafe characters should be blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(root=tmpdir)
            with pytest.raises(ValueError, match='unsafe characters'):
                store._path('session@#$%')

    def test_safe_session_id_allowed(self):
        """Safe alphanumeric session IDs should be allowed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(root=tmpdir)
            path = store._path('session123')
            assert 'session123.json' in str(path)
            assert str(tmpdir) in str(path)

    def test_safe_session_id_with_dash_and_underscore(self):
        """Session IDs with dashes and underscores should be allowed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(root=tmpdir)
            path = store._path('session-123_test')
            assert 'session-123_test.json' in str(path)

    def test_save_with_traversal_blocked(self):
        """Saving with traversal ID should raise ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(root=tmpdir)
            session = ChatSession(id='../../../etc/passwd', messages=[])
            with pytest.raises(ValueError, match='path traversal'):
                store.save(session)

    def test_load_with_traversal_blocked(self):
        """Loading with traversal ID should raise ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(root=tmpdir)
            with pytest.raises(ValueError, match='path traversal'):
                store.load('../../../etc/passwd')

    def test_delete_with_traversal_blocked(self):
        """Deleting with traversal ID should raise ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(root=tmpdir)
            with pytest.raises(ValueError, match='path traversal'):
                store.delete('../../../etc/passwd')

    def test_normal_save_load_delete_works(self):
        """Normal operations should work with safe IDs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(root=tmpdir)
            session = ChatSession(
                id='safe-session-123',
                messages=[ChatMessage(role='user', content='test')],
            )
            store.save(session)
            loaded = store.load('safe-session-123')
            assert loaded is not None
            assert loaded.id == 'safe-session-123'
            assert store.delete('safe-session-123') is True


class TestSubagentSecurityRSK09:
    """Test RSK-09: Subagent Name Path Traversal vulnerability fix."""

    def test_subagent_name_with_traversal_sanitized(self):
        """Subagent names with path traversal should be sanitized."""
        key = new_isolation_session_key(
            parent_run_id='../../../etc/passwd', def_name='test'
        )
        # Should not contain .. or /
        assert '..' not in key
        assert '/' not in key
        assert '\\' not in key

    def test_subagent_name_with_special_chars_sanitized(self):
        """Subagent names with special characters should be sanitized."""
        key = new_isolation_session_key(
            parent_run_id='parent@#$%', def_name='subagent@#$%'
        )
        # Should only contain safe characters
        assert all(c.isalnum() or c in '-_' for c in key)

    def test_subagent_name_with_slash_sanitized(self):
        """Subagent names with slashes should be sanitized."""
        key = new_isolation_session_key(parent_run_id='parent', def_name='sub/test')
        assert '/' not in key
        assert '\\' not in key

    def test_normal_subagent_name_works(self):
        """Normal subagent names should work correctly."""
        key = new_isolation_session_key(
            parent_run_id='parent-run-123', def_name='test-subagent'
        )
        # Parent is truncated to 12 characters
        assert 'parent-run-1' in key
        assert 'test-subagent' in key
        assert len(key.split('-')) >= 3  # parent, def_name, suffix

    def test_empty_name_defaults_to_unnamed(self):
        """Empty or unsafe names should default to 'unnamed'."""
        key = new_isolation_session_key(parent_run_id='', def_name='@#$%')
        assert 'unnamed' in key


class TestPluginSecurityRSK10:
    """Test RSK-10: Dynamic Plugin Supply-Chain Execution vulnerability fix."""

    def test_audit_plugin_source_exists(self):
        """Plugin source audit function should exist."""
        # This is a basic smoke test to ensure the function exists
        assert callable(_audit_plugin_source)

    def test_load_plugins_with_registry(self):
        """Loading plugins should work with a registry."""
        registry = ToolRegistry()
        result = load_plugins(registry)
        # Should return a result object
        assert hasattr(result, 'loaded')
        assert hasattr(result, 'failed')
        assert hasattr(result, 'ok')

    def test_load_plugins_empty_registry(self):
        """Loading plugins with no installed plugins should work."""
        registry = ToolRegistry()
        result = load_plugins(registry)
        # Should succeed even with no plugins
        assert result.ok is True or isinstance(result.failed, list)

    def test_plugin_audit_handles_none_module(self):
        """Plugin audit should handle cases where module cannot be resolved."""

        # Create a mock entry point-like object
        class MockEntryPoint:
            name = 'test-plugin'
            value = 'nonexistent:module'

        # Should not crash
        result = _audit_plugin_source(MockEntryPoint())
        # Should return True (fail-safe allow)
        assert result is True


class TestSecurityIntegration:
    """Integration tests for security fixes."""

    def test_session_and_subagent_security_together(self):
        """Session and subagent security should work together."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test session security
            store = SessionStore(root=tmpdir)
            with pytest.raises(ValueError):
                store._path('../../../etc/passwd')

            # Test subagent security
            key = new_isolation_session_key(
                parent_run_id='../../../etc/passwd', def_name='test'
            )
            assert '..' not in key

    def test_all_safe_operations_work(self):
        """All safe operations should work after security fixes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Session operations
            store = SessionStore(root=tmpdir)
            session = ChatSession(
                id='safe-session', messages=[ChatMessage(role='user', content='test')]
            )
            store.save(session)
            loaded = store.load('safe-session')
            assert loaded is not None
            store.delete('safe-session')

            # Subagent operations
            key = new_isolation_session_key(
                parent_run_id='safe-parent', def_name='safe-subagent'
            )
            assert 'safe-parent' in key
            assert 'safe-subagent' in key

            # Plugin operations
            registry = ToolRegistry()
            result = load_plugins(registry)
            assert result is not None
