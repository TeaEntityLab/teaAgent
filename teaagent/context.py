from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class CompactionResult:
    context: dict[str, Any]
    summary: str
    pinned: dict[str, Any]
    tokens_saved: int


@dataclass
class ContextCompactor:
    """Context compactor with threshold-based auto-compaction.

    Similar to Claude Code's compaction which triggers at 75-92% of context window.
    """

    recent_observations: int = 3
    memory_keys: tuple[str, ...] = field(default_factory=tuple)
    threshold_low: float = 0.75
    threshold_high: float = 0.92

    def should_compact(self, token_count: int, max_tokens: int = 200000) -> bool:
        """Check if compaction should be triggered based on token usage."""
        if max_tokens <= 0:
            return False
        usage = token_count / max_tokens
        return usage >= self.threshold_low

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough approximation: ~4 chars per token)."""
        return len(text) // 4

    def compact(self, context: dict[str, Any]) -> CompactionResult:
        observations = list(context.get('observations', []))
        old_observations = (
            observations[: -self.recent_observations]
            if self.recent_observations
            else observations
        )
        recent = (
            observations[-self.recent_observations :]
            if self.recent_observations
            else []
        )
        pinned = self._collect_pinned(context)
        summary = self._summarize(old_observations)
        tokens_saved = self.estimate_tokens(str(old_observations))
        compacted = dict(context)
        compacted['observations'] = recent
        compacted['compacted_summary'] = summary
        compacted['memory_keys'] = pinned
        compacted['compaction_count'] = context.get('compaction_count', 0) + 1
        return CompactionResult(
            context=compacted, summary=summary, pinned=pinned, tokens_saved=tokens_saved
        )

    def _collect_pinned(self, value: Any) -> dict[str, Any]:
        pinned: dict[str, Any] = {}

        def walk(item: Any) -> None:
            if isinstance(item, dict):
                for key, nested in item.items():
                    if key in self.memory_keys:
                        pinned[key] = nested
                    walk(nested)
            elif isinstance(item, list):
                for nested in item:
                    walk(nested)

        walk(value)
        return pinned

    def _summarize(self, observations: list[dict[str, Any]]) -> str:
        if not observations:
            return ''
        parts = []
        for observation in observations:
            tool_name = observation.get('tool_name', 'unknown_tool')
            result = observation.get('result', {})
            keys = (
                ','.join(sorted(result.keys()))
                if isinstance(result, dict)
                else 'non_object'
            )
            parts.append(f'{tool_name} returned {keys}')
        return '; '.join(parts)


# --- Auto-Compaction Manager ---


@dataclass
class CompactionManager:
    """Manages auto-compaction based on context usage.

    Implements Claude Code-style traffic light zones:
    - Green (0-75%): Normal operation
    - Yellow (75-92%): Hints to user, prepare for compaction
    - Red (92%+): Automatic compaction triggered
    """

    compactor: ContextCompactor = field(default_factory=ContextCompactor)
    max_context_tokens: int = 200000

    def check_and_compact(
        self, context: dict[str, Any], current_tokens: int
    ) -> Optional[CompactionResult]:
        """Check usage and trigger compaction if needed."""
        if not self.compactor.should_compact(current_tokens, self.max_context_tokens):
            return None

        return self.compactor.compact(context)

    def get_usage_level(self, current_tokens: int) -> str:
        """Get current context usage level."""
        if self.max_context_tokens <= 0:
            return 'unknown'
        usage = current_tokens / self.max_context_tokens

        if usage >= self.compactor.threshold_high:
            return 'red'
        if usage >= self.compactor.threshold_low:
            return 'yellow'
        return 'green'

    def get_compaction_hint(self, current_tokens: int) -> Optional[str]:
        """Get user hint based on usage level."""
        level = self.get_usage_level(current_tokens)

        if level == 'red':
            return 'Context nearly full. Compacting...'
        if level == 'yellow':
            return 'Context filling up. Consider saving session.'
        return None
