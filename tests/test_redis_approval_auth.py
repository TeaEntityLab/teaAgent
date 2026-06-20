"""Tests for non-loopback Redis approval queue authentication/TLS enforcement.

Verifies S-P1-2: a non-loopback Redis approval queue must be authenticated
(password) or encrypted (SSL/TLS), mirroring ``require_signature_relay_bind_auth``.
Loopback connections remain backward compatible without auth.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from teaagent.coordination.approval_backend import (
    require_redis_bind_auth,
    resolve_approval_backend,
)
from teaagent.subagents._approval_queue_redis_store import (
    RedisApprovalQueueConfig,
    RedisApprovalQueueStore,
    SecurityError,
)

# ---------------------------------------------------------------------------
# require_redis_bind_auth guard
# ---------------------------------------------------------------------------


class TestRequireRedisBindAuth:
    def test_non_loopback_without_password_or_ssl_raises(self) -> None:
        with pytest.raises(ValueError, match='non-loopback Redis'):
            require_redis_bind_auth('10.0.0.1', None, False)

    def test_non_loopback_with_password_accepted(self) -> None:
        # Should not raise.
        require_redis_bind_auth('10.0.0.1', 's3cret', False)

    def test_non_loopback_with_ssl_accepted(self) -> None:
        # Should not raise.
        require_redis_bind_auth('redis.example.com', None, True)

    def test_non_loopback_with_password_and_ssl_accepted(self) -> None:
        require_redis_bind_auth('redis.example.com', 's3cret', True)

    def test_loopback_without_auth_accepted(self) -> None:
        for host in ('localhost', '127.0.0.1', '::1', '[::1]'):
            require_redis_bind_auth(host, None, False)

    def test_empty_password_treated_as_unauthenticated(self) -> None:
        with pytest.raises(ValueError):
            require_redis_bind_auth('10.0.0.1', '', False)


# ---------------------------------------------------------------------------
# RedisApprovalQueueConfig dataclass validation
# ---------------------------------------------------------------------------


class TestRedisApprovalQueueConfig:
    def test_non_loopback_without_password_or_ssl_raises(self) -> None:
        with pytest.raises(SecurityError, match='non-loopback'):
            RedisApprovalQueueConfig(host='10.0.0.1')

    def test_non_loopback_with_password_accepted(self) -> None:
        config = RedisApprovalQueueConfig(host='10.0.0.1', password='s3cret')
        assert config.password == 's3cret'
        assert config.host == '10.0.0.1'

    def test_non_loopback_with_ssl_accepted(self) -> None:
        config = RedisApprovalQueueConfig(host='redis.example.com', ssl=True)
        assert config.ssl is True

    def test_loopback_without_auth_accepted(self) -> None:
        config = RedisApprovalQueueConfig(host='localhost')
        assert config.host == 'localhost'
        assert config.password is None
        assert config.ssl is False

    def test_default_loopback_config_accepted(self) -> None:
        config = RedisApprovalQueueConfig()
        assert config.host == 'localhost'


# ---------------------------------------------------------------------------
# RedisApprovalQueueStore with mocked Redis client
# ---------------------------------------------------------------------------


def _make_mock_redis_client() -> MagicMock:
    """Create a MagicMock standing in for a redis.Redis client."""
    client = MagicMock()
    client.ping.return_value = True
    client.config_set.return_value = True
    client.info.return_value = {}
    return client


class TestRedisApprovalQueueStoreAuth:
    def test_non_loopback_without_auth_raises_before_connect(self) -> None:
        # The config validation fires before any Redis connection attempt.
        with pytest.raises(SecurityError, match='non-loopback'):
            RedisApprovalQueueConfig(host='10.0.0.1')

    def test_non_loopback_with_password_constructs_store(self) -> None:
        config = RedisApprovalQueueConfig(host='10.0.0.1', password='s3cret')
        mock_client = _make_mock_redis_client()
        # Passing a pre-built client avoids any real network connection.
        store = RedisApprovalQueueStore(config=config, redis_client=mock_client)
        assert store.config.password == 's3cret'

    def test_non_loopback_with_ssl_constructs_store(self) -> None:
        config = RedisApprovalQueueConfig(host='redis.example.com', ssl=True)
        mock_client = _make_mock_redis_client()
        store = RedisApprovalQueueStore(config=config, redis_client=mock_client)
        assert store.config.ssl is True

    def test_loopback_without_auth_constructs_store(self) -> None:
        config = RedisApprovalQueueConfig(host='localhost')
        mock_client = _make_mock_redis_client()
        store = RedisApprovalQueueStore(config=config, redis_client=mock_client)
        assert store.config.host == 'localhost'


# ---------------------------------------------------------------------------
# resolve_approval_backend hybrid path integration
# ---------------------------------------------------------------------------


def _set_hybrid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('TEAAGENT_APPROVAL_COORDINATION_BACKEND', 'hybrid')


class TestResolveApprovalBackendHybridAuth:
    def test_non_loopback_without_password_or_ssl_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _set_hybrid_env(monkeypatch)
        monkeypatch.setenv('TEAAGENT_REDIS_HOST', '10.0.0.1')
        monkeypatch.delenv('TEAAGENT_REDIS_PASSWORD', raising=False)
        monkeypatch.setenv('TEAAGENT_REDIS_SSL', 'false')
        monkeypatch.setenv('TEAAGENT_REDIS_PRIMARY', 'true')

        with pytest.raises((ValueError, SecurityError), match='non-loopback'):
            resolve_approval_backend(tmp_path)

    def test_non_loopback_with_password_accepted(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _set_hybrid_env(monkeypatch)
        monkeypatch.setenv('TEAAGENT_REDIS_HOST', '10.0.0.1')
        monkeypatch.setenv('TEAAGENT_REDIS_PASSWORD', 's3cret')
        monkeypatch.setenv('TEAAGENT_REDIS_SSL', 'false')
        monkeypatch.setenv('TEAAGENT_REDIS_PRIMARY', 'true')
        # Avoid real Redis I/O during construction by patching the hybrid
        # backend's store initialization path. We only need to confirm the
        # auth guard does not raise at resolve time.
        monkeypatch.setattr(
            'teaagent.coordination.approval_hybrid_backend'
            '.HybridApprovalCoordinationBackend.__init__',
            lambda self, **kwargs: None,
        )

        backend = resolve_approval_backend(tmp_path)
        assert backend is not None

    def test_non_loopback_with_ssl_accepted(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _set_hybrid_env(monkeypatch)
        monkeypatch.setenv('TEAAGENT_REDIS_HOST', 'redis.example.com')
        monkeypatch.delenv('TEAAGENT_REDIS_PASSWORD', raising=False)
        monkeypatch.setenv('TEAAGENT_REDIS_SSL', 'true')
        monkeypatch.setenv('TEAAGENT_REDIS_PRIMARY', 'true')
        monkeypatch.setattr(
            'teaagent.coordination.approval_hybrid_backend'
            '.HybridApprovalCoordinationBackend.__init__',
            lambda self, **kwargs: None,
        )

        backend = resolve_approval_backend(tmp_path)
        assert backend is not None

    def test_loopback_without_auth_accepted(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _set_hybrid_env(monkeypatch)
        monkeypatch.setenv('TEAAGENT_REDIS_HOST', 'localhost')
        monkeypatch.delenv('TEAAGENT_REDIS_PASSWORD', raising=False)
        monkeypatch.setenv('TEAAGENT_REDIS_SSL', 'false')
        monkeypatch.setenv('TEAAGENT_REDIS_PRIMARY', 'true')
        monkeypatch.setattr(
            'teaagent.coordination.approval_hybrid_backend'
            '.HybridApprovalCoordinationBackend.__init__',
            lambda self, **kwargs: None,
        )

        backend = resolve_approval_backend(tmp_path)
        assert backend is not None
