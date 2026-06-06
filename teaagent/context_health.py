"""Context-health score for long-session awareness (CTX-001).

Computes a health score from token pressure, stale files, old observations,
memory confidence, and hidden large attachments.  Used by the operator cockpit
and run evidence.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class ContextHealthScore:
    """Aggregate context-health score with component signals.

    ``overall`` is the worst component status — any single RED signal
    makes the overall score RED.
    """

    overall: str = 'unknown'  # green | yellow | red | unknown
    token_pressure: str = 'unknown'
    stale_files: int = 0
    old_observations: int = 0
    memory_confidence: str = 'unknown'
    hidden_large_attachments: int = 0
    recommendation: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'overall': self.overall,
            'token_pressure': self.token_pressure,
            'stale_files': self.stale_files,
            'old_observations': self.old_observations,
            'memory_confidence': self.memory_confidence,
            'hidden_large_attachments': self.hidden_large_attachments,
            'recommendation': self.recommendation,
        }


# ── Component signal helpers ─────────────────────────────────────────────


def _compute_token_pressure(
    used_tokens: int,
    max_tokens: int,
) -> str:
    """Map token usage to a traffic-light signal."""
    if max_tokens <= 0:
        return 'unknown'
    ratio = used_tokens / max_tokens
    if ratio >= 0.92:
        return 'red'
    if ratio >= 0.75:
        return 'yellow'
    return 'green'


def _compute_memory_confidence(memory_catalog: Any) -> str:
    """Score memory freshness from a MemoryCatalog-like object.

    Returns:
        ``"green"`` — most memories are recent (< 1 day old).
        ``"yellow"`` — some memories are stale (1-7 days).
        ``"red"`` — majority of memories are old (> 7 days).
        ``"unknown"`` — cannot determine.
    """
    if memory_catalog is None:
        return 'unknown'
    try:
        entries = list(memory_catalog) if hasattr(memory_catalog, '__iter__') else []
    except Exception:
        return 'unknown'

    if not entries:
        return 'green'

    now = time.time()
    recent = sum(1 for e in entries if _entry_age_seconds(e, now) < 86400)
    stale = sum(1 for e in entries if _entry_age_seconds(e, now) > 604800)

    total = len(entries)
    if stale > total * 0.5:
        return 'red'
    if recent < total * 0.3:
        return 'yellow'
    return 'green'


def _entry_age_seconds(entry: Any, now: float) -> float:
    """Extract age in seconds from a memory entry."""
    try:
        ts = entry.get('updated_at') or entry.get('created_at') or 0
        return now - (ts if isinstance(ts, (int, float)) else 0)
    except Exception:
        return float('inf')


# ── Public API ───────────────────────────────────────────────────────────


def compute_context_health(
    *,
    session_tokens_used: int = 0,
    session_max_tokens: int = 200_000,
    workspace_root: Optional[str] = None,
    observation_count: int = 0,
    memory_catalog: Any = None,
    large_attachment_threshold_bytes: int = 1_000_000,
) -> ContextHealthScore:
    """Compute a context-health score for the current session.

    Args:
        session_tokens_used: Estimated token usage so far.
        session_max_tokens: Model context window limit.
        workspace_root: Root of the workspace (for stale-file detection).
        observation_count: Number of observations accumulated.
        memory_catalog: Optional MemoryCatalog-like object for memory freshness.
        large_attachment_threshold_bytes: Files above this size are flagged.

    Returns:
        A ``ContextHealthScore`` dataclass.
    """
    tp = _compute_token_pressure(session_tokens_used, session_max_tokens)

    # Stale files: detect files modified since the session started.
    stale = _count_stale_workspace_files(workspace_root)

    # Old observations: arbitrary age threshold — an observation is "old"
    # if the count is very high (proxy: >50 observations means compaction
    # has probably happened).
    old_obs = max(0, observation_count - 50)

    mc = _compute_memory_confidence(memory_catalog)

    # Hidden large attachments: files > threshold in workspace root.
    hidden = _count_large_files(workspace_root, large_attachment_threshold_bytes)

    signals = [tp]
    if stale > 0:
        signals.append('yellow' if stale < 10 else 'red')
    if old_obs > 100:
        signals.append('red')
    elif old_obs > 50:
        signals.append('yellow')
    if mc == 'red':
        signals.append('red')
    elif mc == 'yellow':
        signals.append('yellow')

    overall = _worst_signal(signals)

    rec = _build_recommendation(overall, tp, stale, old_obs, mc, hidden)

    return ContextHealthScore(
        overall=overall,
        token_pressure=tp,
        stale_files=stale,
        old_observations=old_obs,
        memory_confidence=mc,
        hidden_large_attachments=hidden,
        recommendation=rec,
    )


def _worst_signal(signals: list[str]) -> str:
    """Return the worst signal from a list."""
    if 'red' in signals:
        return 'red'
    if 'yellow' in signals:
        return 'yellow'
    if 'green' in signals:
        return 'green'
    return 'unknown'


def _count_stale_workspace_files(workspace_root: Optional[str]) -> int:
    """Count files modified in the last hour under workspace root."""
    if not workspace_root:
        return 0
    root = Path(workspace_root)
    if not root.is_dir():
        return 0
    cutoff = time.time() - 3600  # 1 hour
    count = 0
    try:
        for entry in root.iterdir():
            if entry.is_file():
                mtime = entry.stat().st_mtime
                if mtime > cutoff:
                    count += 1
            if count >= 100:  # cap
                break
    except (OSError, PermissionError):
        pass
    return count


def _count_large_files(
    workspace_root: Optional[str],
    threshold: int,
) -> int:
    """Count files over *threshold* bytes under workspace root (limit=50)."""
    if not workspace_root:
        return 0
    root = Path(workspace_root)
    if not root.is_dir():
        return 0
    count = 0
    try:
        for entry in root.iterdir():
            if entry.is_file() and entry.stat().st_size > threshold:
                count += 1
            if count >= 50:
                break
    except (OSError, PermissionError):
        pass
    return count


def _build_recommendation(
    overall: str,
    token_pressure: str,
    stale_files: int,
    old_observations: int,
    memory_confidence: str,
    hidden_large_attachments: int,
) -> str:
    """Build a human-readable recommendation based on component signals."""
    parts: list[str] = []
    if token_pressure == 'red':
        parts.append('Context nearly full — consider starting a fresh session')
    elif token_pressure == 'yellow':
        parts.append('Context filling up')

    if stale_files > 0:
        parts.append(f'{stale_files} file(s) changed on disk — context may be stale')

    if old_observations > 100:
        parts.append('Very high observation count — compaction recommended')
    elif old_observations > 50:
        parts.append('High observation count')

    if memory_confidence == 'red':
        parts.append('Most memories are stale — consider pruning')
    elif memory_confidence == 'yellow':
        parts.append('Some memories may be outdated')

    if hidden_large_attachments > 0:
        parts.append(
            f'{hidden_large_attachments} large file(s) — may cause token spikes'
        )

    return ' | '.join(parts) if parts else 'Context health is good'
