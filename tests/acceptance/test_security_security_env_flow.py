"""Acceptance: security_env environment-gated security posture flags.

Security boundary: dev signatures must only be allowed when explicitly enabled.
Happy path: all gates default to off/None when env vars are unset.
Edge case: truthy values are correctly parsed across '1'/'true'/'yes'/'on'."""

from __future__ import annotations

import os
from unittest.mock import patch

from teaagent.security_env import (
    allow_dev_signatures,
    federated_signature_token,
    plugins_strict_audit,
    signature_relay_api_token,
    strict_local_services,
)


class TestAllowDevSignatures:
    def test_default_false(self, monkeypatch):
        monkeypatch.delenv('TEAAGENT_ALLOW_DEV_SIGNATURES', raising=False)
        assert allow_dev_signatures() is False

    def test_truthy_values(self):
        for val in ('1', 'true', 'yes', 'on', 'True', 'YES'):
            with patch.dict(os.environ, {'TEAAGENT_ALLOW_DEV_SIGNATURES': val}):
                assert allow_dev_signatures() is True, f'failed for {val}'

    def test_falsy_values(self):
        for val in ('0', 'false', 'no', 'off', ''):
            with patch.dict(os.environ, {'TEAAGENT_ALLOW_DEV_SIGNATURES': val}):
                assert allow_dev_signatures() is False, f'failed for {val}'


class TestStrictLocalServices:
    def test_default_false(self, monkeypatch):
        monkeypatch.delenv('TEAAGENT_STRICT_LOCAL', raising=False)
        assert strict_local_services() is False

    def test_truthy_enables(self):
        with patch.dict(os.environ, {'TEAAGENT_STRICT_LOCAL': '1'}):
            assert strict_local_services() is True


class TestPluginsStrictAudit:
    def test_default_false(self, monkeypatch):
        monkeypatch.delenv('TEAAGENT_PLUGINS_STRICT', raising=False)
        assert plugins_strict_audit() is False

    def test_truthy_enables(self):
        with patch.dict(os.environ, {'TEAAGENT_PLUGINS_STRICT': 'true'}):
            assert plugins_strict_audit() is True


class TestSignatureRelayApiToken:
    def test_default_none(self, monkeypatch):
        monkeypatch.delenv('TEAAGENT_SIGNATURE_RELAY_TOKEN', raising=False)
        monkeypatch.delenv('TEAAGENT_RELAY_TOKEN', raising=False)
        assert signature_relay_api_token() is None

    def test_primary_env_var(self):
        with patch.dict(os.environ, {'TEAAGENT_SIGNATURE_RELAY_TOKEN': 'abc123'}):
            assert signature_relay_api_token() == 'abc123'

    def test_fallback_env_var(self):
        with patch.dict(os.environ, {'TEAAGENT_RELAY_TOKEN': 'fallback'}):
            assert signature_relay_api_token() == 'fallback'

    def test_primary_takes_precedence(self):
        env = {
            'TEAAGENT_SIGNATURE_RELAY_TOKEN': 'primary',
            'TEAAGENT_RELAY_TOKEN': 'fallback',
        }
        with patch.dict(os.environ, env):
            assert signature_relay_api_token() == 'primary'


class TestFederatedSignatureToken:
    def test_default_none(self, monkeypatch):
        monkeypatch.delenv('TEAAGENT_FEDERATED_SIGNATURE_TOKEN', raising=False)
        assert federated_signature_token() is None

    def test_set_returns_value(self):
        with patch.dict(os.environ, {'TEAAGENT_FEDERATED_SIGNATURE_TOKEN': 'secret'}):
            assert federated_signature_token() == 'secret'

    def test_empty_string_returns_none(self):
        with patch.dict(os.environ, {'TEAAGENT_FEDERATED_SIGNATURE_TOKEN': ''}):
            assert federated_signature_token() is None
