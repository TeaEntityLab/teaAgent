"""Approach hint generator for tournament subagents.

This module provides:
- Keyword extraction from task descriptions
- Mapping to approach templates
- Generation of distinct approach hints
"""

from __future__ import annotations

from typing import List


class ApproachHintGenerator:
    """Generator for approach hints in tournament mode."""

    # Common approach templates for different task types
    APPROACH_TEMPLATES = {
        'optimize': [
            'Use indexing to improve query performance',
            'Refactor the algorithm for better time complexity',
            'Add caching to reduce redundant computations',
            'Use data structures more efficiently',
        ],
        'refactor': [
            'Extract common patterns into helper functions',
            'Apply design patterns to improve structure',
            'Simplify complex logic with better abstractions',
            'Improve code readability and maintainability',
        ],
        'fix': [
            'Identify and correct the root cause',
            'Add defensive programming and error handling',
            'Improve edge case handling',
            'Add comprehensive logging for debugging',
        ],
        'add': [
            'Implement with minimal dependencies',
            'Follow existing code patterns and conventions',
            'Add comprehensive documentation',
            'Include unit tests for new functionality',
        ],
        'default': [
            'Approach 1: Focus on simplicity and clarity',
            'Approach 2: Focus on performance and efficiency',
            'Approach 3: Focus on extensibility and maintainability',
        ],
    }

    def __init__(self) -> None:
        """Initialize approach hint generator."""
        # No initialization needed; hints are generated dynamically based on task

    def generate_hints(self, task: str, count: int) -> List[str]:
        """Generate approach hints for tournament.

        Args:
            task: The task description
            count: Number of hints to generate

        Returns:
            List of approach hints
        """
        # Extract keywords from task
        task_lower = task.lower()

        # Determine task type
        task_type = 'default'
        for keyword in ['optimize', 'refactor', 'fix', 'add']:
            if keyword in task_lower:
                task_type = keyword
                break

        # Get templates for task type
        templates = self.APPROACH_TEMPLATES.get(
            task_type, self.APPROACH_TEMPLATES['default']
        )

        # Generate hints
        hints = []
        for i in range(count):
            if i < len(templates):
                hints.append(templates[i])
            else:
                # Generate generic hints if we need more
                hints.append(
                    f'Approach {i + 1}: Explore alternative implementation strategy'
                )

        return hints[:count]
