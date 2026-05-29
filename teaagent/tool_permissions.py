"""Tool Permission Control - JIT approval for destructive tools.

This module implements safety controls for tool access:
1. Classifies tools by destructive potential
2. Enforces safe defaults for dynamic agents
3. Implements JIT approval for destructive tool access
4. Integrates with ToolRegistry for permission enforcement
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class ToolSafetyLevel(Enum):
    """Tool safety classification."""

    SAFE = 'safe'  # Read-only, no side effects
    INSPECT = 'inspect'  # Analysis tools, minimal side effects
    DESTRUCTIVE = 'destructive'  # Can modify state, requires approval


@dataclass
class ToolPermission:
    """Permission metadata for a tool."""

    name: str
    safety_level: ToolSafetyLevel
    description: str = ''
    requires_approval: bool = False


@dataclass
class PermissionRequest:
    """A request for tool access approval."""

    tool_name: str
    agent_name: str
    reason: str
    approved: bool = False
    approval_token: Optional[str] = None


class ToolPermissionManager:
    """Manages tool permissions and JIT approval flow."""

    def __init__(
        self,
        approval_callback: Optional[Callable[[PermissionRequest], bool]] = None,
    ) -> None:
        self._approval_callback = approval_callback
        self._tool_permissions: dict[str, ToolPermission] = {}
        self._agent_tool_whitelist: dict[str, set[str]] = {}
        self._agent_approved_tools: dict[str, set[str]] = {}
        self._initialize_default_permissions()

    def _initialize_default_permissions(self) -> None:
        """Initialize default safety classifications for common tools."""
        # Safe tools (read-only)
        safe_tools = [
            'read_file',
            'workspace_read_file',
            'grep',
            'search',
            'list_directory',
            'get_file_info',
            'cx_overview',
            'cx_symbols',
            'cx_definition',
            'cx_references',
        ]

        # Inspect tools (analysis, minimal side effects)
        inspect_tools = [
            'python_repl',
            'shell',
            'git_diff',
            'git_log',
            'git_status',
            'lint',
            'typecheck',
        ]

        # Destructive tools (require approval)
        destructive_tools = [
            'write_file',
            'workspace_write_file',
            'delete_file',
            'bash_mutate',
            'git_commit',
            'git_push',
            'run_command',
            'execute',
        ]

        for tool in safe_tools:
            self._tool_permissions[tool] = ToolPermission(
                name=tool, safety_level=ToolSafetyLevel.SAFE
            )

        for tool in inspect_tools:
            self._tool_permissions[tool] = ToolPermission(
                name=tool, safety_level=ToolSafetyLevel.INSPECT
            )

        for tool in destructive_tools:
            self._tool_permissions[tool] = ToolPermission(
                name=tool,
                safety_level=ToolSafetyLevel.DESTRUCTIVE,
                requires_approval=True,
            )

    def register_tool_permission(
        self,
        permission: ToolPermission,
        *,
        allow_downgrade: bool = False,
    ) -> None:
        """Register or update tool permission metadata.

        Args:
            permission: Tool permission to register.
            allow_downgrade: If False (default), prevent downgrading a DESTRUCTIVE
                tool to SAFE or INSPECT. Set to True only for intentional reclassification.
        """
        existing = self._tool_permissions.get(permission.name)
        if (
            existing is not None
            and not allow_downgrade
            and existing.safety_level == ToolSafetyLevel.DESTRUCTIVE
            and permission.safety_level != ToolSafetyLevel.DESTRUCTIVE
        ):
            logger.warning(
                f'Blocked downgrade of {permission.name} from DESTRUCTIVE to '
                f'{permission.safety_level.value}. Use allow_downgrade=True to override.'
            )
            return
        self._tool_permissions[permission.name] = permission

    def get_tool_permission(self, tool_name: str) -> Optional[ToolPermission]:
        """Get permission metadata for a tool.

        Args:
            tool_name: Name of the tool.

        Returns:
            ToolPermission if found, None otherwise.
        """
        return self._tool_permissions.get(tool_name)

    def classify_tool(self, tool_name: str) -> ToolSafetyLevel:
        """Classify a tool by safety level.

        Args:
            tool_name: Name of the tool.

        Returns:
            ToolSafetyLevel classification.
        """
        permission = self.get_tool_permission(tool_name)
        if permission:
            return permission.safety_level

        # Default to destructive for unknown tools (safe default)
        logger.warning(f'Unknown tool {tool_name}, defaulting to DESTRUCTIVE')
        return ToolSafetyLevel.DESTRUCTIVE

    def grant_agent_tool_access(
        self,
        agent_name: str,
        tool_names: tuple[str, ...],
        allow_destructive: bool = False,
    ) -> None:
        """Grant an agent access to specific tools.

        Args:
            agent_name: Name of the agent.
            tool_names: Tools to grant access to.
            allow_destructive: If False, filter out destructive tools.
        """
        allowed_tools = set()

        for tool_name in tool_names:
            safety_level = self.classify_tool(tool_name)

            if safety_level == ToolSafetyLevel.DESTRUCTIVE and not allow_destructive:
                logger.info(
                    f'Filtered destructive tool {tool_name} for agent {agent_name}'
                )
                continue

            allowed_tools.add(tool_name)

        self._agent_tool_whitelist[agent_name] = allowed_tools
        logger.info(f'Granted {len(allowed_tools)} tools to agent {agent_name}')

    def check_tool_access(
        self, agent_name: str, tool_name: str
    ) -> tuple[bool, Optional[str]]:
        """Check if an agent has access to a tool.

        Args:
            agent_name: Name of the agent.
            tool_name: Name of the tool.

        Returns:
            Tuple of (has_access, denial_reason).
        """
        # Check if tool is in agent's whitelist
        agent_tools = self._agent_tool_whitelist.get(agent_name, set())
        if tool_name not in agent_tools:
            return False, f'Tool {tool_name} not in agent whitelist'

        # Check if tool requires JIT approval
        permission = self.get_tool_permission(tool_name)
        if permission and permission.requires_approval:
            # Check if this specific agent has JIT approval for this tool
            agent_approved = self._agent_approved_tools.get(agent_name, set())
            if tool_name in agent_approved:
                return True, None
            return False, f'Tool {tool_name} requires JIT approval'

        return True, None

    def request_tool_approval(
        self, agent_name: str, tool_name: str, reason: str
    ) -> PermissionRequest:
        """Request JIT approval for a destructive tool.

        Args:
            agent_name: Name of the agent requesting access.
            tool_name: Name of the tool.
            reason: Reason for the request.

        Returns:
            PermissionRequest with approval status.
        """
        request = PermissionRequest(
            tool_name=tool_name, agent_name=agent_name, reason=reason
        )

        if self._approval_callback:
            try:
                approved = self._approval_callback(request)
                request.approved = approved
            except Exception as exc:
                logger.error(f'Approval callback failed: {exc}')
                request.approved = False
        else:
            # Default: deny if no callback
            logger.warning('No approval callback set, denying request')
            request.approved = False

        if request.approved:
            # Add to whitelist for this agent
            agent_tools = self._agent_tool_whitelist.get(agent_name, set())
            agent_tools.add(tool_name)
            self._agent_tool_whitelist[agent_name] = agent_tools

            # Track per-agent JIT approval (does NOT mutate global tool permissions)
            agent_approved = self._agent_approved_tools.get(agent_name, set())
            agent_approved.add(tool_name)
            self._agent_approved_tools[agent_name] = agent_approved

        return request

    def revoke_agent_tool_access(self, agent_name: str, tool_name: str) -> None:
        """Revoke an agent's access to a specific tool.

        Args:
            agent_name: Name of the agent.
            tool_name: Name of the tool to revoke.
        """
        agent_tools = self._agent_tool_whitelist.get(agent_name)
        if agent_tools and tool_name in agent_tools:
            agent_tools.remove(tool_name)
            logger.info(f'Revoked {tool_name} access for agent {agent_name}')
        agent_approved = self._agent_approved_tools.get(agent_name)
        if agent_approved:
            agent_approved.discard(tool_name)

    def get_agent_tools(self, agent_name: str) -> set[str]:
        """Get all tools an agent has access to.

        Args:
            agent_name: Name of the agent.

        Returns:
            Set of tool names.
        """
        return self._agent_tool_whitelist.get(agent_name, set()).copy()

    def apply_safe_defaults(
        self, agent_name: str, requested_tools: tuple[str, ...]
    ) -> tuple[str, ...]:
        """Apply safe defaults to filter destructive tools.

        Args:
            agent_name: Name of the agent.
            requested_tools: Tools the agent requested.

        Returns:
            Filtered tuple of safe tools only.
        """
        self.grant_agent_tool_access(
            agent_name, requested_tools, allow_destructive=False
        )
        return tuple(self.get_agent_tools(agent_name))
