from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CompactionResult:
    context: dict[str, Any]
    summary: str
    pinned: dict[str, Any]


@dataclass(frozen=True)
class ContextCompactor:
    recent_observations: int = 3
    memory_keys: tuple[str, ...] = field(default_factory=tuple)

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
        compacted = dict(context)
        compacted['observations'] = recent
        compacted['compacted_summary'] = summary
        compacted['memory_keys'] = pinned
        return CompactionResult(context=compacted, summary=summary, pinned=pinned)

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
