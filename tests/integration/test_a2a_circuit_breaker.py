"""IT: A2A FederatedAgentRegistry circuit breaker.

After ``failure_threshold`` consecutive fetch failures for one endpoint the
circuit opens and that endpoint is skipped.  After ``reset_timeout_seconds``
the circuit half-opens and the next refresh retries the endpoint.
"""

from __future__ import annotations

import os
import time
from unittest.mock import patch

from teaagent.agentcard import (
    CircuitBreakerConfig,
    FederatedAgentRegistry,
)

# Configurable timeout for circuit breaker reset tests
# Can be overridden via environment variable for slow CI systems
# Default is conservative (1.0s) to avoid flakiness on slow CI systems
_CIRCUIT_RESET_WAIT_SECONDS = float(
    os.environ.get('TEAAGENT_TEST_CIRCUIT_RESET_WAIT', '1.0')
)

# Circuit breaker test constants
_CIRCUIT_FAILURE_THRESHOLD_STANDARD = (
    2  # Standard failure threshold for circuit opening
)
_CIRCUIT_FAILURE_THRESHOLD_LOW = 1  # Low failure threshold for quick circuit opening
_CIRCUIT_FAILURE_THRESHOLD_HIGH = 3  # High failure threshold for flaky endpoint test
_CIRCUIT_RESET_TIMEOUT_LONG = 60.0  # Long reset timeout (seconds) for standard tests
_CIRCUIT_NO_CIRCUIT_BREAKER_CALL_COUNT = (
    3  # Expected call count when no circuit breaker
)

_CARD_DATA = {
    'name': 'agent-alpha',
    'version': '1.0.0',
    'description': 'test',
    'capabilities': ['tool_execution'],
    'tools': [],
    'endpoint': 'http://alpha.local',
}


def _ok_fetch(
    url, timeout=10, allow_http=False, max_redirects=5, data=None, headers=None
):
    """safe_urlopen replacement that succeeds."""

    class _Resp:
        def read(self):
            import json

            return json.dumps(_CARD_DATA).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    return _Resp()


def _fail_fetch(
    url, timeout=10, allow_http=False, max_redirects=5, data=None, headers=None
):
    raise OSError('connection refused')


def test_circuit_opens_after_threshold():
    cb = CircuitBreakerConfig(
        failure_threshold=_CIRCUIT_FAILURE_THRESHOLD_STANDARD,
        reset_timeout_seconds=_CIRCUIT_RESET_TIMEOUT_LONG,
    )
    reg = FederatedAgentRegistry(
        ['http://bad.local'], circuit_breaker=cb, allow_http=True
    )

    with patch('teaagent.agentcard.safe_urlopen', side_effect=_fail_fetch):
        reg.refresh()  # failure 1
        reg.refresh()  # failure 2 → circuit opens

    state = reg.circuit_state('http://bad.local')
    assert state == 'open'


def test_open_circuit_skips_endpoint():
    cb = CircuitBreakerConfig(
        failure_threshold=_CIRCUIT_FAILURE_THRESHOLD_LOW,
        reset_timeout_seconds=_CIRCUIT_RESET_TIMEOUT_LONG,
    )
    reg = FederatedAgentRegistry(
        ['http://bad.local', 'http://good.local'],
        circuit_breaker=cb,
        allow_http=True,
    )
    call_log: list[str] = []

    def selective_fetch(
        url, timeout=10, allow_http=False, max_redirects=5, data=None, headers=None
    ):
        call_log.append(url)
        if 'bad' in url:
            raise OSError('bad')
        return _ok_fetch(url)

    with patch('teaagent.agentcard.safe_urlopen', side_effect=selective_fetch):
        reg.refresh()  # bad fails → circuit opens; good succeeds
        call_log.clear()
        reg.refresh()  # bad should be skipped

    # bad.local well-known URL should NOT appear in the second refresh
    assert not any('bad.local' in u for u in call_log)


def test_success_resets_failure_count():
    cb = CircuitBreakerConfig(
        failure_threshold=_CIRCUIT_FAILURE_THRESHOLD_HIGH,
        reset_timeout_seconds=_CIRCUIT_RESET_TIMEOUT_LONG,
    )
    reg = FederatedAgentRegistry(
        ['http://flaky.local'], circuit_breaker=cb, allow_http=True
    )

    fail_count = {'n': 0}

    def flaky(
        url, timeout=10, allow_http=False, max_redirects=5, data=None, headers=None
    ):
        fail_count['n'] += 1
        if fail_count['n'] < 2:
            raise OSError('flaky')
        return _ok_fetch(url)

    with patch('teaagent.agentcard.safe_urlopen', side_effect=flaky):
        reg.refresh()  # fail 1
        reg.refresh()  # success → reset
        reg.refresh()  # success

    state = reg.circuit_state('http://flaky.local')
    assert state == 'closed'


def test_circuit_resets_after_timeout():
    # Use a short timeout that's 2x the configurable wait time
    cb = CircuitBreakerConfig(
        failure_threshold=1, reset_timeout_seconds=_CIRCUIT_RESET_WAIT_SECONDS / 2
    )
    reg = FederatedAgentRegistry(
        ['http://temp-bad.local'], circuit_breaker=cb, allow_http=True
    )

    with patch('teaagent.agentcard.safe_urlopen', side_effect=_fail_fetch):
        reg.refresh()  # opens circuit

    assert reg.circuit_state('http://temp-bad.local') == 'open'

    time.sleep(_CIRCUIT_RESET_WAIT_SECONDS)  # wait for reset (configurable)

    # After timeout, circuit should allow a retry
    with patch(
        'teaagent.agentcard.safe_urlopen',
        return_value=_ok_fetch('http://temp-bad.local'),
    ):
        reg.refresh()

    assert reg.circuit_state('http://temp-bad.local') == 'closed'


def test_no_circuit_breaker_behaves_as_before():
    """Without circuit_breaker, FederatedAgentRegistry retries every time."""
    reg = FederatedAgentRegistry(['http://always-fail.local'], allow_http=True)
    call_count = {'n': 0}

    def counting_fail(
        url, timeout=10, allow_http=False, max_redirects=5, data=None, headers=None
    ):
        call_count['n'] += 1
        raise OSError('down')

    with patch('teaagent.agentcard.safe_urlopen', side_effect=counting_fail):
        reg.refresh()
        reg.refresh()
        reg.refresh()

    assert call_count['n'] >= _CIRCUIT_NO_CIRCUIT_BREAKER_CALL_COUNT  # no skipping


def test_cards_from_healthy_endpoints_still_returned():
    cb = CircuitBreakerConfig(
        failure_threshold=_CIRCUIT_FAILURE_THRESHOLD_LOW,
        reset_timeout_seconds=_CIRCUIT_RESET_TIMEOUT_LONG,
    )
    reg = FederatedAgentRegistry(
        ['http://bad.local', 'http://good.local'],
        circuit_breaker=cb,
        allow_http=True,
    )

    def selective(
        url, timeout=10, allow_http=False, max_redirects=5, data=None, headers=None
    ):
        if 'bad' in url:
            raise OSError('bad')
        return _ok_fetch(url)

    with patch('teaagent.agentcard.safe_urlopen', side_effect=selective):
        errors = reg.refresh()
        cards = reg.list_cards()

    # bad endpoint error recorded, good card still present
    assert any('bad.local' in e for e in errors)
    assert any(c.name == 'agent-alpha' for c in cards)


def test_circuit_state_for_unknown_endpoint_is_closed():
    reg = FederatedAgentRegistry(['http://known.local'])
    assert reg.circuit_state('http://unknown.local') == 'closed'
