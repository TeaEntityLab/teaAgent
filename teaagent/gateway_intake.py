"""Gateway Intake - Converts incoming webhooks/messages into structured execution plans."""

from __future__ import annotations

from typing import Any, Optional

from teaagent.coordinator import TaskCoordinator, WorkflowPlan
from teaagent.gateway import GatewayMessage
from teaagent.plugin_system import PluginRegistry


class GatewayIntakeParser:
    """Parses incoming gateway messages and webhooks into structured WorkflowPlans."""

    def __init__(
        self, plugin_registry: PluginRegistry, llm_adapter: Optional[Any] = None
    ) -> None:
        self.coordinator = TaskCoordinator(plugin_registry, llm_adapter)

    def parse_message(self, msg: GatewayMessage) -> Optional[WorkflowPlan]:
        """Convert a GatewayMessage into a WorkflowPlan if it represents a valid task request."""
        text = msg.text.strip()
        # Support various command shapes:
        # @teaagent run: <task>
        # /run <task>
        # run <task>
        task_desc = None
        if text.startswith('@teaagent run:'):
            task_desc = text[len('@teaagent run:') :].strip()
        elif text.startswith('@teaagent run'):
            task_desc = text[len('@teaagent run') :].strip()
        elif text.startswith('/run '):
            task_desc = text[len('/run ') :].strip()
        elif text.startswith('run '):
            task_desc = text[len('run ') :].strip()
        else:
            # Fallback if text contains clear task action keywords
            lower = text.lower()
            if any(
                keyword in lower
                for keyword in (
                    'implement',
                    'fix',
                    'refactor',
                    'test',
                    'review',
                    'clean',
                    'documentation',
                )
            ):
                task_desc = text

        if not task_desc:
            return None

        classification, plan = self.coordinator.route_task(task_desc)
        return plan

    def parse_webhook_payload(self, payload: dict[str, Any]) -> Optional[WorkflowPlan]:
        """Parse a generic webhook payload (e.g. from Slack or custom webhook) into a WorkflowPlan."""
        # Slack event subscription payload structure
        if 'event' in payload:
            event = payload['event']
            text = event.get('text', '')
            msg = GatewayMessage(
                platform='slack',
                channel_id=event.get('channel', 'unknown'),
                user_id=event.get('user', 'unknown'),
                text=text,
            )
            return self.parse_message(msg)

        # Custom JSON payload structure
        text = payload.get('text') or payload.get('message') or payload.get('task')
        if text:
            msg = GatewayMessage(
                platform=payload.get('platform', 'generic'),
                channel_id=payload.get('channel_id', 'unknown'),
                user_id=payload.get('user_id', 'unknown'),
                text=text,
            )
            return self.parse_message(msg)

        return None
