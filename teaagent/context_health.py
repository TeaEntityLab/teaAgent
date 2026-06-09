"""Long-session context health tests for extended agent interactions (TASK-H5-001-04).

This module provides tests for evaluating context health during long sessions,
including context retention, memory leak detection, and context drift detection.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from .eval_suite import EvalCategory, EvalTest


class ContextHealthMetric(str, Enum):
    """Types of context health metrics."""

    RETENTION = 'retention'  # Context retention over time
    CONSISTENCY = 'consistency'  # Context consistency across turns
    LEAKAGE = 'leakage'  # Memory leak detection
    DRIFT = 'drift'  # Context drift detection
    RELEVANCE = 'relevance'  # Context relevance to current task


@dataclass
class ContextHealthTest:
    """A context health test case."""

    test_id: str
    name: str
    session_length: int  # Number of turns in the session
    context_window_size: int  # Maximum context window size
    expected_retention_rate: float = 0.9  # Expected retention rate
    max_memory_growth: float = 1.5  # Max memory growth factor
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'test_id': self.test_id,
            'name': self.name,
            'session_length': self.session_length,
            'context_window_size': self.context_window_size,
            'expected_retention_rate': self.expected_retention_rate,
            'max_memory_growth': self.max_memory_growth,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ContextHealthTest':
        """Create from dictionary."""
        return cls(
            test_id=data['test_id'],
            name=data['name'],
            session_length=data['session_length'],
            context_window_size=data['context_window_size'],
            expected_retention_rate=data.get('expected_retention_rate', 0.9),
            max_memory_growth=data.get('max_memory_growth', 1.5),
            metadata=data.get('metadata', {}),
        )


@dataclass
class ContextHealthResult:
    """Result of a context health test."""

    test_id: str
    actual_retention_rate: float = 0.0
    consistency_score: float = 0.0
    memory_growth_factor: float = 0.0
    drift_score: float = 0.0
    relevance_score: float = 0.0
    overall_health_score: float = 0.0
    passed: bool = False
    health_metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'test_id': self.test_id,
            'actual_retention_rate': self.actual_retention_rate,
            'consistency_score': self.consistency_score,
            'memory_growth_factor': self.memory_growth_factor,
            'drift_score': self.drift_score,
            'relevance_score': self.relevance_score,
            'overall_health_score': self.overall_health_score,
            'passed': self.passed,
            'health_metrics': self.health_metrics,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ContextHealthResult':
        """Create from dictionary."""
        return cls(
            test_id=data['test_id'],
            actual_retention_rate=data.get('actual_retention_rate', 0.0),
            consistency_score=data.get('consistency_score', 0.0),
            memory_growth_factor=data.get('memory_growth_factor', 0.0),
            drift_score=data.get('drift_score', 0.0),
            relevance_score=data.get('relevance_score', 0.0),
            overall_health_score=data.get('overall_health_score', 0.0),
            passed=data.get('passed', False),
            health_metrics=data.get('health_metrics', {}),
        )


class ContextHealthEvaluator:
    """Evaluator for context health tests."""

    def __init__(self) -> None:
        """Initialize the context health evaluator."""
        pass

    def calculate_retention_rate(
        self,
        initial_context: list[str],
        final_context: list[str],
    ) -> float:
        """Calculate context retention rate.

        Args:
            initial_context: Initial context items.
            final_context: Final context items.

        Returns:
            Retention rate between 0.0 and 1.0.
        """
        if not initial_context:
            return 1.0

        initial_set = set(initial_context)
        final_set = set(final_context)

        retained = len(initial_set.intersection(final_set))
        return retained / len(initial_set)

    def calculate_consistency_score(
        self,
        context_history: list[list[str]],
    ) -> float:
        """Calculate context consistency score across turns.

        Args:
            context_history: List of context states for each turn.

        Returns:
            Consistency score between 0.0 and 1.0.
        """
        if len(context_history) < 2:
            return 1.0

        consistency_scores = []

        for i in range(1, len(context_history)):
            prev_context = set(context_history[i - 1])
            curr_context = set(context_history[i])

            # Calculate Jaccard similarity
            intersection = len(prev_context.intersection(curr_context))
            union = len(prev_context.union(curr_context))

            if union > 0:
                similarity = intersection / union
                consistency_scores.append(similarity)

        return (
            sum(consistency_scores) / len(consistency_scores)
            if consistency_scores
            else 1.0
        )

    def calculate_memory_growth(
        self,
        initial_memory_size: int,
        final_memory_size: int,
    ) -> float:
        """Calculate memory growth factor.

        Args:
            initial_memory_size: Initial memory size in bytes.
            final_memory_size: Final memory size in bytes.

        Returns:
            Memory growth factor.
        """
        if initial_memory_size == 0:
            return 1.0

        return final_memory_size / initial_memory_size

    def calculate_drift_score(
        self,
        initial_context: list[str],
        final_context: list[str],
    ) -> float:
        """Calculate context drift score.

        Args:
            initial_context: Initial context items.
            final_context: Final context items.

        Returns:
            Drift score between 0.0 (no drift) and 1.0 (high drift).
        """
        initial_set = set(initial_context)
        final_set = set(final_context)

        if not initial_set:
            return 0.0

        # Calculate how much new content was added
        new_content = final_set - initial_set
        drift = len(new_content) / len(initial_set)

        return min(drift, 1.0)

    def calculate_relevance_score(
        self,
        current_task: str,
        context: list[str],
    ) -> float:
        """Calculate context relevance to current task.

        Args:
            current_task: Current task description.
            context: Current context items.

        Returns:
            Relevance score between 0.0 and 1.0.
        """
        if not context:
            return 0.0

        task_keywords = set(current_task.lower().split())
        relevant_count = 0

        for context_item in context:
            context_keywords = set(context_item.lower().split())
            if task_keywords.intersection(context_keywords):
                relevant_count += 1

        return relevant_count / len(context)

    def evaluate_context_health(
        self,
        test: ContextHealthTest,
        session_data: dict[str, Any],
    ) -> ContextHealthResult:
        """Evaluate context health for a test.

        Args:
            test: Context health test to evaluate.
            session_data: Session data including context history.

        Returns:
            Context health result.
        """
        result = ContextHealthResult(test_id=test.test_id)

        # Extract session data
        initial_context = session_data.get('initial_context', [])
        final_context = session_data.get('final_context', [])
        context_history = session_data.get('context_history', [])
        initial_memory = session_data.get('initial_memory_size', 0)
        final_memory = session_data.get('final_memory_size', 0)
        current_task = session_data.get('current_task', '')

        # Calculate metrics
        result.actual_retention_rate = self.calculate_retention_rate(
            initial_context,
            final_context,
        )

        result.consistency_score = self.calculate_consistency_score(context_history)

        result.memory_growth_factor = self.calculate_memory_growth(
            initial_memory,
            final_memory,
        )

        result.drift_score = self.calculate_drift_score(
            initial_context,
            final_context,
        )

        result.relevance_score = self.calculate_relevance_score(
            current_task,
            final_context,
        )

        # Calculate overall health score
        health_scores = [
            result.actual_retention_rate,
            result.consistency_score,
            1.0 - result.drift_score,  # Invert drift (lower is better)
            result.relevance_score,
        ]
        result.overall_health_score = sum(health_scores) / len(health_scores)

        # Determine if passed
        retention_ok = result.actual_retention_rate >= test.expected_retention_rate
        memory_ok = result.memory_growth_factor <= test.max_memory_growth
        health_ok = result.overall_health_score >= 0.7

        result.passed = retention_ok and memory_ok and health_ok

        # Health metrics
        result.health_metrics = {
            'retention_ok': retention_ok,
            'memory_ok': memory_ok,
            'health_ok': health_ok,
            'session_length': test.session_length,
            'context_window_size': test.context_window_size,
        }

        return result

    def create_default_context_health_tests(self) -> list[ContextHealthTest]:
        """Create default context health tests.

        Returns:
            List of default context health tests.
        """
        tests = []

        # Test 1: Short session
        test1 = ContextHealthTest(
            test_id='health-001',
            name='Short Session - 10 turns',
            session_length=10,
            context_window_size=1000,
            expected_retention_rate=0.95,
            max_memory_growth=1.2,
        )
        tests.append(test1)

        # Test 2: Medium session
        test2 = ContextHealthTest(
            test_id='health-002',
            name='Medium Session - 50 turns',
            session_length=50,
            context_window_size=2000,
            expected_retention_rate=0.9,
            max_memory_growth=1.5,
        )
        tests.append(test2)

        # Test 3: Long session
        test3 = ContextHealthTest(
            test_id='health-003',
            name='Long Session - 100 turns',
            session_length=100,
            context_window_size=5000,
            expected_retention_rate=0.85,
            max_memory_growth=2.0,
        )
        tests.append(test3)

        return tests

    def convert_to_eval_test(self, health_test: ContextHealthTest) -> EvalTest:
        """Convert a context health test to an eval test.

        Args:
            health_test: Context health test to convert.

        Returns:
            Eval test.
        """
        return EvalTest(
            test_id=health_test.test_id,
            name=health_test.name,
            category=EvalCategory.LONG_SESSION,
            description=f'Context health test: {health_test.name}',
            metadata={
                'session_length': health_test.session_length,
                'context_window_size': health_test.context_window_size,
                'expected_retention_rate': health_test.expected_retention_rate,
                'max_memory_growth': health_test.max_memory_growth,
            },
        )


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
