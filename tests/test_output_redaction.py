"""Regression tests for central CLI JSON output redaction (CodeQL #39).

`teaagent.cli._output.print_json` is the shared logging sink for CLI handlers.
It must redact sensitive data two ways:

1. Key-based: values under sensitive-sounding keys (api_token, password, ...).
2. Value-based: strings whose *shape* is a known credential (Bearer tokens,
   provider key prefixes, JWTs) even when they sit under a benign key.

The value-based pass is the defense-in-depth fix for clear-text logging of
secrets that leak as values under non-sensitive keys. It is intentionally
conservative so opaque identifiers (run ids, SHAs) are NOT redacted.
"""

from __future__ import annotations

import json
from uuid import uuid4

from teaagent.cli._output import _redact_value, print_json

_REDACTED = '***REDACTED***'


def test_redacts_bearer_token_under_benign_key() -> None:
    out = _redact_value({'message': 'Bearer abcd1234.efgh5678.ijkl'})
    assert out == {'message': _REDACTED}


def test_redacts_provider_key_prefixes_under_benign_key() -> None:
    for secret in (
        'sk-ABC123def456ghi789',
        'ghp_0123456789abcdefghij',
        'github_pat_0123456789abcdef',
        'xoxb-0123-4567-abcdef',
        'AKIAIOSFODNN7EXAMPLE',
    ):
        out = _redact_value({'note': secret})
        assert out == {'note': _REDACTED}, secret


def test_redacts_jwt_under_benign_key() -> None:
    jwt = 'eyJhbGciOiJIUzI1.eyJzdWIiOiIxMjM0.SflKxwRJSMeKKF2QT4'
    out = _redact_value({'detail': jwt})
    assert out == {'detail': _REDACTED}


def test_redacts_credential_embedded_in_error_message() -> None:
    out = _redact_value({'message': 'request failed with sk-ABC123def456ghi789'})
    assert out == {'message': _REDACTED}


def test_redacts_duplicate_value_learned_from_sensitive_key() -> None:
    out = _redact_value(
        {'api_token': 'opaque-secret-123', 'message': 'opaque-secret-123'}
    )
    assert out == {'api_token': _REDACTED, 'message': _REDACTED}


def test_key_based_redaction_still_applies() -> None:
    out = _redact_value({'api_token': 'whatever', 'password': 'hunter2'})
    assert out == {'api_token': _REDACTED, 'password': _REDACTED}


def test_does_not_redact_opaque_run_id_hex() -> None:
    run_id = uuid4().hex
    out = _redact_value({'run_id': run_id})
    assert out == {'run_id': run_id}


def test_does_not_over_redact_benign_values() -> None:
    payload = {
        'provider': 'gpt',
        'permission_mode': 'read-only',
        'input_tokens': 200,
        'output_tokens': 80,
        'usage_level': 'green',
        'cmd': 'cat /etc/hosts && echo done',
        'status': 'completed',
    }
    assert _redact_value(payload) == payload


def test_redaction_recurses_through_lists_and_nested_dicts() -> None:
    out = _redact_value({'events': [{'msg': 'Bearer xyz'}, {'run_id': 'run-123'}]})
    assert out == {'events': [{'msg': _REDACTED}, {'run_id': 'run-123'}]}


def test_print_json_emits_redacted_payload(capsys) -> None:
    print_json({'log': 'sk-ABC123def456ghi789', 'run_id': 'run-1'})
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload == {'log': _REDACTED, 'run_id': 'run-1'}
