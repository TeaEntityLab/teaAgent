"""Coordinator CLI handlers."""

from __future__ import annotations

import argparse

from teaagent.coordinator import TaskCoordinator
from teaagent.plugin_system import PluginRegistry


def classify_command(args: argparse.Namespace) -> int:
    """Classify a task by type and complexity."""
    try:
        registry = PluginRegistry()
        coordinator = TaskCoordinator(registry)
        classification = coordinator.classify_task(args.task)

        print(f'Task: {args.task}')
        print(f'Type: {classification.task_type.value}')
        print(f'Complexity: {classification.complexity.value}')
        print(f'Confidence: {classification.confidence:.0%}')
        if classification.suggested_agent:
            print(f'Suggested Agent: {classification.suggested_agent}')
        print(f'Requires Multi-Step: {classification.requires_multi_step}')
        print(f'Estimated Steps: {classification.estimated_steps}')

        return 0
    except Exception as exc:
        print(f'Error: {exc}')
        return 1
