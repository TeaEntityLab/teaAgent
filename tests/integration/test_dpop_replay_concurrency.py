"""IT-15: DPoP replay cache is correct under concurrent access.

Verifies that:
- The same jti cannot be consumed twice even under concurrent requests.
- Expired entries are evicted and the same jti can be used again after TTL.
- Different JTIs do not interfere.

Uses ``DPoPReplayCache`` directly (no external server required).
Requires the ``cryptography`` package; skipped otherwise.
"""

from __future__ import annotations

import threading
import time
import uuid

import pytest

HAS_CRYPTOGRAPHY = False
try:
    from cryptography.hazmat.primitives.asymmetric import ec  # noqa: F401

    HAS_CRYPTOGRAPHY = True
except ImportError:
    pass

pytestmark = pytest.mark.skipif(
    not HAS_CRYPTOGRAPHY, reason='cryptography not installed'
)


def test_dpop_replay_cache_blocks_reuse():
    """Two concurrent requests with identical jti: exactly one must succeed."""
    from teaagent.oauth21._replay import DPoPReplayCache
    from teaagent.oauth21._types import InvalidDPoPError

    cache = DPoPReplayCache()
    jti = uuid.uuid4().hex
    now = time.time()
    successes: list[bool] = []
    errors: list[Exception] = []
    lock = threading.Lock()

    def try_remember():
        try:
            cache.remember_once(jti, iat=now, now=now, ttl=60.0)
            with lock:
                successes.append(True)
        except InvalidDPoPError as exc:
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=try_remember) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(successes) == 1, f'Expected exactly 1 success, got {len(successes)}'
    assert len(errors) == 9, f'Expected 9 replay errors, got {len(errors)}'


def test_dpop_replay_cache_different_jtis_do_not_interfere():
    """Different JTIs should all succeed (no cross-contamination)."""
    from teaagent.oauth21._replay import DPoPReplayCache

    cache = DPoPReplayCache()
    now = time.time()
    jtis = [uuid.uuid4().hex for _ in range(5)]
    for jti in jtis:
        cache.remember_once(jti, iat=now, now=now, ttl=60.0)  # must not raise


def test_dpop_replay_cache_expired_entry_evicted():
    """After TTL, the eviction logic removes the entry (no raise on expiry check)."""
    from teaagent.oauth21._replay import DPoPReplayCache

    cache = DPoPReplayCache()
    jti = uuid.uuid4().hex
    old_time = time.time() - 120  # 2 minutes ago

    # Record the jti with a timestamp 2 minutes in the past
    cache.remember_once(jti, iat=old_time, now=old_time, ttl=60.0)

    # Now call with current time; the old entry should be evicted by the TTL sweep
    # and the same jti can be used again
    now = time.time()
    cache.remember_once(jti, iat=now, now=now, ttl=60.0)  # must not raise


def test_dpop_replay_cache_missing_jti_raises():
    """Empty or non-string jti raises InvalidDPoPError."""
    from teaagent.oauth21._replay import DPoPReplayCache
    from teaagent.oauth21._types import InvalidDPoPError

    cache = DPoPReplayCache()
    now = time.time()
    with pytest.raises(InvalidDPoPError, match='missing jti'):
        cache.remember_once('', iat=now, now=now, ttl=60.0)

    with pytest.raises(InvalidDPoPError, match='missing jti'):
        cache.remember_once(None, iat=now, now=now, ttl=60.0)
