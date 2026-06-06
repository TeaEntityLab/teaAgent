"""Scope budget for plan-bound execution (PLAN-002).

A scope budget constrains what an agent can do during a run — which files
it may read/write, which shell commands it may run, what counts as
out-of-scope, risk appetite, and cost/time budgets.

Enforcement blocks out-of-scope actions or asks for explicit expansion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any, Optional


@dataclass
class ScopeBudget:
    """Budget constraints for a plan-bound run.

    All fields are optional — an unset (``None``) field means "no
    restriction".  Enforcement uses the most restrictive combination
    of applicable fields.
    """

    # ── file access ──
    allowed_files: Optional[list[str]] = None
    """Glob patterns for files the agent may read or write, e.g.
    ``["src/**/*.py", "tests/**"]``.  ``None`` = unrestricted."""

    # ── shell commands ──
    allowed_commands: Optional[list[str]] = None
    """Shell command prefixes the agent may execute, e.g.
    ``["pytest", "ruff", "python src/"]``.  ``None`` = unrestricted."""

    # ── scope markers ──
    non_goals: list[str] = field(default_factory=list)
    """Explicit non-goals that the agent must not work on, e.g.
    ``["refactor CI pipeline", "update README"]``."""

    # ── risk / cost / time caps ──
    max_risk_level: Optional[str] = None  # "low" | "medium" | "high"
    """Maximum allowable risk level.  Destructive operations above this
    level are blocked."""

    max_spend_cents: Optional[float] = None
    """Maximum total spend for the run in cents."""

    max_duration_seconds: Optional[float] = None
    """Maximum wall-clock duration for the run in seconds."""

    def to_dict(self) -> dict[str, Any]:
        return {
            'allowed_files': self.allowed_files,
            'allowed_commands': self.allowed_commands,
            'non_goals': self.non_goals,
            'max_risk_level': self.max_risk_level,
            'max_spend_cents': self.max_spend_cents,
            'max_duration_seconds': self.max_duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> Optional[ScopeBudget]:
        if data is None:
            return None
        return cls(
            allowed_files=data.get('allowed_files'),
            allowed_commands=data.get('allowed_commands'),
            non_goals=data.get('non_goals', []),
            max_risk_level=data.get('max_risk_level'),
            max_spend_cents=(
                float(data['max_spend_cents'])
                if data.get('max_spend_cents') is not None
                else None
            ),
            max_duration_seconds=(
                float(data['max_duration_seconds'])
                if data.get('max_duration_seconds') is not None
                else None
            ),
        )


# ── Enforcement result ──────────────────────────────────────────────────


class ScopeVeto(Exception):
    """Raised when an action violates the scope budget."""

    def __init__(self, reason: str, field: str = 'general'):
        self.reason = reason
        self.field = field
        super().__init__(f'[scope:{field}] {reason}')


@dataclass
class ScopeCheckResult:
    """Result of a scope budget check."""

    allowed: bool
    reason: str = ''
    field: str = ''


# ── Enforcement helpers ─────────────────────────────────────────────────


def _matches_any_glob(path: str, patterns: Optional[list[str]]) -> bool:
    """Check if *path* matches any glob in *patterns*.

    Supports ``**`` for recursive matching (zero or more directory levels).
    A pattern without directory separators matches the filename in any
    directory (like ``gitignore`` behaviour).
    """
    if patterns is None:
        return True  # unrestricted
    if not patterns:
        return False  # empty = deny all
    posix_path = path.replace('\\', '/')
    return any(_path_matches_glob(posix_path, pat) for pat in patterns)


def _path_matches_glob(path: str, pattern: str) -> bool:
    """Match *path* against *pattern* with ``**`` support."""
    # PurePosixPath.match treats ** as one-or-more dirs, so for the
    # zero-directory case we also try without the **/.
    # E.g. "src/main.py" should match "src/**/*.py".
    if '**' in pattern:
        return (
            PurePosixPath(path).match(pattern)
            or PurePosixPath(path).match(pattern.replace('**/', ''))
            or PurePosixPath(path).match(pattern.replace('**', '*'))
        )
    return PurePosixPath(path).match(pattern)


def _matches_any_command_prefix(command: str, prefixes: Optional[list[str]]) -> bool:
    """Check if *command* starts with any allowed prefix."""
    if prefixes is None:
        return True
    if not prefixes:
        return False
    cmd_stripped = command.strip()
    return any(cmd_stripped.startswith(prefix) for prefix in prefixes)


# ── Risk level ordering ─────────────────────────────────────────────────

_RISK_ORDER = {'low': 0, 'medium': 1, 'high': 2}


def _risk_exceeds(actual: str, max_level: Optional[str]) -> bool:
    """Return True if *actual* exceeds the allowed *max_level*."""
    if max_level is None:
        return False
    actual_val = _RISK_ORDER.get(actual, 99)
    max_val = _RISK_ORDER.get(max_level, 0)
    return actual_val > max_val


# ── Public API ──────────────────────────────────────────────────────────


def check_file_access(
    file_path: str,
    budget: ScopeBudget,
) -> ScopeCheckResult:
    """Check if *file_path* is within the scope budget's file access."""
    if budget.allowed_files is None:
        return ScopeCheckResult(allowed=True)

    if _matches_any_glob(file_path, budget.allowed_files):
        return ScopeCheckResult(allowed=True)

    allowed_str = ', '.join(budget.allowed_files) if budget.allowed_files else '(none)'
    return ScopeCheckResult(
        allowed=False,
        reason=f"File '{file_path}' is not in allowed_files [{allowed_str}]",
        field='allowed_files',
    )


def check_command(
    command: str,
    budget: ScopeBudget,
) -> ScopeCheckResult:
    """Check if *command* is within the scope budget's allowed commands."""
    if budget.allowed_commands is None:
        return ScopeCheckResult(allowed=True)

    if _matches_any_command_prefix(command, budget.allowed_commands):
        return ScopeCheckResult(allowed=True)

    allowed_str = (
        ', '.join(budget.allowed_commands) if budget.allowed_commands else '(none)'
    )
    return ScopeCheckResult(
        allowed=False,
        reason=f"Command '{command}' is not in allowed_commands [{allowed_str}]",
        field='allowed_commands',
    )


def check_non_goal(
    action_description: str,
    budget: ScopeBudget,
) -> ScopeCheckResult:
    """Check if *action_description* matches a declared non-goal."""
    if not budget.non_goals:
        return ScopeCheckResult(allowed=True)

    action_lower = action_description.lower()
    for ng in budget.non_goals:
        if ng.lower() in action_lower:
            return ScopeCheckResult(
                allowed=False,
                reason=f"Action matches non-goal: '{ng}'",
                field='non_goals',
            )
    return ScopeCheckResult(allowed=True)


def check_risk_level(
    risk_level: str,
    budget: ScopeBudget,
) -> ScopeCheckResult:
    """Check if *risk_level* exceeds the budget's ``max_risk_level``."""
    if _risk_exceeds(risk_level, budget.max_risk_level):
        return ScopeCheckResult(
            allowed=False,
            reason=f"Risk level '{risk_level}' exceeds max '{budget.max_risk_level}'",
            field='max_risk_level',
        )
    return ScopeCheckResult(allowed=True)


def check_spend(
    spent_cents: float,
    budget: ScopeBudget,
) -> ScopeCheckResult:
    """Check if *spent_cents* exceeds the budget's spend cap."""
    if budget.max_spend_cents is None:
        return ScopeCheckResult(allowed=True)
    if spent_cents > budget.max_spend_cents:
        return ScopeCheckResult(
            allowed=False,
            reason=(
                f'Spent ${spent_cents / 100:.2f} exceeds '
                f'max ${budget.max_spend_cents / 100:.2f}'
            ),
            field='max_spend_cents',
        )
    return ScopeCheckResult(allowed=True)


def check_duration(
    elapsed_seconds: float,
    budget: ScopeBudget,
) -> ScopeCheckResult:
    """Check if *elapsed_seconds* exceeds the duration cap."""
    if budget.max_duration_seconds is None:
        return ScopeCheckResult(allowed=True)
    if elapsed_seconds > budget.max_duration_seconds:
        return ScopeCheckResult(
            allowed=False,
            reason=(
                f'Duration {elapsed_seconds:.0f}s exceeds '
                f'max {budget.max_duration_seconds:.0f}s'
            ),
            field='max_duration_seconds',
        )
    return ScopeCheckResult(allowed=True)


# ── Tool-aware enforcement ──────────────────────────────────────────────

_TOOL_FILE_ARGS: dict[str, str] = {
    'read_file': 'file_path',
    'write_file': 'file_path',
    'workspace_read_file': 'file_path',
    'workspace_write_file': 'file_path',
    'apply_patch': 'file_path',
    'edit_file': 'file_path',
}

_TOOL_COMMAND_ARGS: dict[str, str] = {
    'shell': 'command',
    'workspace_run_shell_mutate': 'command',
    'workspace_run_shell_inspect': 'command',
    'bash': 'command',
    'execute_command': 'command',
}


def check_tool_call(
    tool_name: str,
    tool_args: dict[str, Any],
    budget: ScopeBudget,
) -> list[ScopeCheckResult]:
    """Run scope-budget checks for a tool call.

    Automatically maps common tool names to the correct check type:
    - File-access tools (read_file, write_file, …) → ``check_file_access``
    - Shell tools (shell, bash, …) → ``check_command``

    For other tools use the ``check_all`` function directly.
    """
    results: list[ScopeCheckResult] = []

    # File access check
    file_arg = _TOOL_FILE_ARGS.get(tool_name)
    if file_arg and file_arg in tool_args:
        results.append(check_file_access(str(tool_args[file_arg]), budget))

    # Command check
    cmd_arg = _TOOL_COMMAND_ARGS.get(tool_name)
    if cmd_arg and cmd_arg in tool_args:
        results.append(check_command(str(tool_args[cmd_arg]), budget))

    return results


class ScopeBudgetEnforcer:
    """Scope budget enforcer that can be queried by the runner.

    Usage::

        enforcer = ScopeBudgetEnforcer(budget)
        for result in enforcer.check_file("src/main.py"):
            if not result.allowed:
                raise ScopeVeto(result.reason, result.field)
    """

    def __init__(self, budget: Optional[ScopeBudget] = None):
        self._budget = budget

    @property
    def budget(self) -> Optional[ScopeBudget]:
        return self._budget

    @budget.setter
    def budget(self, value: Optional[ScopeBudget]) -> None:
        self._budget = value

    @property
    def active(self) -> bool:
        """True when a budget is set and at least one constraint is active."""
        return self._budget is not None and any(
            [
                self._budget.allowed_files is not None,
                self._budget.allowed_commands is not None,
                self._budget.non_goals,
                self._budget.max_risk_level is not None,
                self._budget.max_spend_cents is not None,
                self._budget.max_duration_seconds is not None,
            ]
        )

    def check_file(self, file_path: str) -> list[ScopeCheckResult]:
        if not self._budget:
            return [ScopeCheckResult(allowed=True)]
        return [check_file_access(file_path, self._budget)]

    def check_command(self, command: str) -> list[ScopeCheckResult]:
        if not self._budget:
            return [ScopeCheckResult(allowed=True)]
        return [check_command(command, self._budget)]

    def check_tool(
        self, tool_name: str, tool_args: dict[str, Any]
    ) -> list[ScopeCheckResult]:
        if not self._budget:
            return [ScopeCheckResult(allowed=True)]
        return check_tool_call(tool_name, tool_args, self._budget)


def check_all(
    *,
    file_path: Optional[str] = None,
    command: Optional[str] = None,
    action_description: Optional[str] = None,
    risk_level: Optional[str] = None,
    spent_cents: Optional[float] = None,
    elapsed_seconds: Optional[float] = None,
    budget: ScopeBudget,
) -> list[ScopeCheckResult]:
    """Run all applicable scope checks against *budget*.

    Returns a list of check results.  Any result with ``allowed=False``
    means the action should be blocked.
    """
    results: list[ScopeCheckResult] = []

    if file_path is not None:
        results.append(check_file_access(file_path, budget))

    if command is not None:
        results.append(check_command(command, budget))

    if action_description is not None:
        results.append(check_non_goal(action_description, budget))

    if risk_level is not None:
        results.append(check_risk_level(risk_level, budget))

    if spent_cents is not None:
        results.append(check_spend(spent_cents, budget))

    if elapsed_seconds is not None:
        results.append(check_duration(elapsed_seconds, budget))

    return results
