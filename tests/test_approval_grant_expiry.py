# test-type: contract
"""ApprovalGrant.is_expired is the public expiry check used by the cockpit."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from teaagent.ergonomics._approval_grants import ApprovalGrant


def _grant(expires_at: str | None) -> ApprovalGrant:
    return ApprovalGrant(
        grant_id='g1',
        tool_name='workspace_write_file',
        scope='session',
        expires_at=expires_at,
    )


def test_grant_without_expiry_never_expires() -> None:
    assert _grant(None).is_expired() is False


def test_grant_expires_once_expiry_has_passed() -> None:
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    assert _grant(past).is_expired() is True
    assert _grant(future).is_expired() is False


def test_naive_expiry_is_read_as_utc() -> None:
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).replace(tzinfo=None)
    assert _grant(past.isoformat()).is_expired() is True


def test_unparseable_expiry_counts_as_expired() -> None:
    assert _grant('not-a-timestamp').is_expired() is True
