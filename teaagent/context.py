from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class CompactionResult:
    context: dict[str, Any]
    summary: str
    pinned: dict[str, Any]
    tokens_saved: int
    compression_ratio: float = 0.0


@dataclass
class ContextCompactor:
    """Context compactor with threshold-based auto-compaction and semantic compression.

    Similar to Claude Code's compaction which triggers at 75-92% of context window.
    Enhanced with semantic summarization for long conversations.
    """

    recent_observations: int = 3
    memory_keys: tuple[str, ...] = field(default_factory=tuple)
    threshold_low: float = 0.75
    threshold_high: float = 0.92
    enable_semantic_compression: bool = True
    max_summary_length: int = 500

    def should_compact(self, token_count: int, max_tokens: int = 200000) -> bool:
        """Check if compaction should be triggered based on token usage."""
        if max_tokens <= 0:
            return False
        usage = token_count / max_tokens
        return usage >= self.threshold_low

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count (improved approximation: ~4 chars per token for code, ~3.5 for text)."""
        if not text:
            return 0
        # Better estimation based on content type
        code_ratio = sum(1 for c in text if c in '{}[]();:,.') / max(len(text), 1)
        chars_per_token = 3.5 if code_ratio < 0.1 else 4.0
        return int(len(text) / chars_per_token)

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

        if self.enable_semantic_compression:
            summary = self._semantic_summarize(old_observations)
        else:
            summary = self._summarize(old_observations)

        tokens_saved = self.estimate_tokens(str(old_observations))
        tokens_summary = self.estimate_tokens(summary)
        compression_ratio = (
            tokens_summary / max(tokens_saved, 1) if tokens_saved > 0 else 0.0
        )

        compacted = dict(context)
        compacted['observations'] = recent
        compacted['compacted_summary'] = summary
        compacted['memory_keys'] = pinned
        compacted['compaction_count'] = context.get('compaction_count', 0) + 1
        compacted['compression_ratio'] = compression_ratio
        return CompactionResult(
            context=compacted,
            summary=summary,
            pinned=pinned,
            tokens_saved=tokens_saved,
            compression_ratio=compression_ratio,
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

    def _semantic_summarize(self, observations: list[dict[str, Any]]) -> str:
        """Generate semantic summary of observations with key insights extraction."""
        if not observations:
            return ''

        # Group observations by tool type
        tool_groups: dict[str, list[dict[str, Any]]] = {}
        for obs in observations:
            tool_name = obs.get('tool_name', 'unknown')
            if tool_name not in tool_groups:
                tool_groups[tool_name] = []
            tool_groups[tool_name].append(obs)

        # Generate semantic summary per tool group
        summary_parts = []
        for tool_name, group in tool_groups.items():
            if tool_name == 'read_file':
                files = [obs.get('result', {}).get('path', 'unknown') for obs in group]
                summary_parts.append(
                    f'Read {len(files)} files: {", ".join(files[:3])}{"..." if len(files) > 3 else ""}'
                )
            elif tool_name == 'search_text':
                total_matches = sum(
                    len(obs.get('result', {}).get('matches', [])) for obs in group
                )
                summary_parts.append(
                    f'Searched text with {total_matches} matches across {len(group)} queries'
                )
            elif tool_name == 'edit_file':
                files_edited = len(
                    set(obs.get('result', {}).get('path', 'unknown') for obs in group)
                )
                summary_parts.append(f'Edited {files_edited} files')
            elif tool_name == 'bash':
                commands = [
                    obs.get('result', {}).get('command', 'unknown') for obs in group
                ]
                summary_parts.append(
                    f'Executed {len(commands)} commands: {", ".join(commands[:2])}{"..." if len(commands) > 2 else ""}'
                )
            else:
                summary_parts.append(f'{tool_name}: {len(group)} operations')

        summary = '; '.join(summary_parts)

        # Truncate if too long
        if len(summary) > self.max_summary_length:
            summary = summary[: self.max_summary_length - 3] + '...'

        return summary

    def compact_chat_history(
        self, messages: list[dict[str, Any]], max_tokens: int
    ) -> list[dict[str, Any]]:
        """Compact chat history using sliding window with semantic preservation.

        Args:
            messages: List of chat messages with 'role' and 'content'
            max_tokens: Maximum tokens to retain in history

        Returns:
            Compacted message list preserving system prompt and recent context
        """
        if not messages:
            return []

        # Always keep system message
        system_messages = [m for m in messages if m.get('role') == 'system']
        user_assistant = [m for m in messages if m.get('role') in ('user', 'assistant')]

        current_tokens = sum(
            self.estimate_tokens(m.get('content', '')) for m in user_assistant
        )

        if current_tokens <= max_tokens:
            return messages

        # Use sliding window to fit within budget
        compacted = list(system_messages)
        tokens_used = sum(
            self.estimate_tokens(m.get('content', '')) for m in system_messages
        )

        # Keep most recent messages first
        for msg in reversed(user_assistant):
            msg_tokens = self.estimate_tokens(msg.get('content', ''))
            if tokens_used + msg_tokens <= max_tokens:
                compacted.insert(len(system_messages), msg)
                tokens_used += msg_tokens
            else:
                break

        # Add summary of omitted messages if significant content was dropped
        omitted_count = len(user_assistant) - (len(compacted) - len(system_messages))
        if omitted_count > 2:
            summary_msg = {
                'role': 'system',
                'content': f'[Context compaction: {omitted_count} earlier messages omitted to fit token budget. Key context preserved in recent messages.]',
            }
            compacted.insert(len(system_messages), summary_msg)

        return compacted


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
