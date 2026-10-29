"""Workspace, tenant and symlink containment for tool path arguments.

Mixin for ``ApprovalManager``. The methods and class attribute are moved unchanged
from ``teaagent.approval.manager`` (A-P1-6 split, ADR-0044). They keep their names
and ``self`` semantics, so existing callers and test call paths are unchanged. The
fail-closed rules (containment first, symlink components denied, OSError denied)
are not edited.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from teaagent.errors import DenialReasonCode, ToolPermissionError


class _PathContainmentMixin:
    """Containment checks shared by ApprovalManager; see module docstring."""

    # Declarations only (no value, no runtime attribute): set by ApprovalManager.__init__.
    workspace_root: str
    tenant_id: str
    _extra_path_keys: set[str]

    # Path argument keys checked for workspace containment.
    _PATH_ARGUMENT_KEYS: tuple[str, ...] = ('path', 'file_path', 'target_path', 'file')

    def _assert_tenant_paths_match(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> None:
        """Enforce that runs under a tenant cannot access files/paths belonging to other tenants."""
        values = []

        def collect_values(val: Any) -> None:
            if isinstance(val, (str, Path)):
                values.append(val)
            elif isinstance(val, dict):
                for v in val.values():
                    collect_values(v)
            elif isinstance(val, (list, tuple, set)):
                for v in val:
                    collect_values(v)

        collect_values(arguments)

        for val in values:
            val_str = str(val)
            try:
                resolved_val = Path(val_str).resolve()
            except Exception:
                continue

            parts = resolved_val.parts

            # Determine the path's owner tenant (if any)
            owner_tenant = None
            if 'tenants' in parts:
                idx = parts.index('tenants')
                if idx + 1 < len(parts):
                    owner_tenant = parts[idx + 1]
            else:
                if '.teaagent' in parts:
                    idx = parts.index('.teaagent')
                    if idx + 1 < len(parts):
                        sub = parts[idx + 1]
                        if sub in (
                            'runs',
                            'undo',
                            'background',
                            'run-keys',
                            'audit-encryption',
                        ):
                            owner_tenant = 'default'

            if owner_tenant is not None and owner_tenant != self.tenant_id:
                raise ToolPermissionError(
                    f"Tenant mismatch: Tool '{tool_name}' target path '{val_str}' "
                    f"belongs to tenant '{owner_tenant}', which does not match active tenant '{self.tenant_id}'.",
                    reason_code=DenialReasonCode.WORKSPACE_WRITE_MODE,
                )

    def _get_extended_path_keys(self) -> set[str]:
        """Return the full set of path argument keys (defaults + extensions)."""
        return set(self._PATH_ARGUMENT_KEYS) | self._extra_path_keys

    @staticmethod
    def _looks_like_path(value: Any) -> bool:
        """Return True if *value* heuristically looks like a filesystem path.

        A value is considered path-like when it is a ``Path`` object or a
        standalone string containing ``/`` or ``\\``.  Strings that contain
        spaces (e.g. shell commands like ``/usr/bin/python -m pytest``) are
        intentionally excluded — they are compound expressions, not single
        path arguments, and checking their entire body as one path would
        produce false positives.
        """
        if isinstance(value, Path):
            return True
        if isinstance(value, str) and value.strip():
            s = value.strip()
            if '/' in s or '\\' in s:
                return ' ' not in s
        return False

    @staticmethod
    def _has_symlink_component(root: Path, relative: str) -> bool:
        """Return True if any component of *relative* (resolved against *root*) is a symlink."""
        try:
            current = root
            for part in Path(relative).parts:
                if part == '..':
                    current = current.parent
                    continue
                current = current / part
                if current.is_symlink():
                    return True
        except ValueError:
            return False
        except OSError:
            # Fail closed (owner decision 2026-10-27, approval split-plan Q6, F3):
            # a component whose symlink status cannot be read is treated as unsafe.
            return True
        return False

    def _assert_paths_in_workspace(
        self,
        tool_name: str,
        call_id: str,
        arguments: dict[str, Any],
    ) -> None:
        """Check that tool path arguments stay within workspace_root.

        Two-phase check:
        1. Named path keys (default + extra_path_keys) are checked directly.
        2. ALL string/Path values are checked heuristically — any value
           containing ``/`` or ``\\`` (or that is a Path object) is validated
           for workspace containment.

        Raises ToolPermissionError if any path argument resolves outside
        the workspace root. This ensures explicit workspace root takes
        precedence over saved/imported state.
        """
        root_path = Path(self.workspace_root).resolve()
        key_set = self._get_extended_path_keys()

        for key, raw in arguments.items():
            if self._looks_like_path(raw):
                path_str = raw if isinstance(raw, str) else str(raw)
                # Containment is the primary boundary: check it first so paths
                # that resolve outside the workspace report "outside workspace
                # root" regardless of any symlink ancestor (e.g. system paths
                # like /etc on macOS, where /etc is itself a symlink). .resolve()
                # follows symlinks, so out-of-workspace symlink escapes are
                # still caught here. The symlink-component check below is then
                # defense-in-depth for paths that resolve *inside* the workspace.
                try:
                    target = (root_path / path_str).resolve()
                    target.relative_to(root_path)
                except (ValueError, OSError):
                    raise ToolPermissionError(
                        f"Tool '{tool_name}' target path '{path_str}' is outside "
                        f"workspace root '{self.workspace_root}'. "
                        'Explicit workspace root must take precedence '
                        'over any saved state.',
                        reason_code=DenialReasonCode.WORKSPACE_WRITE_MODE,
                    ) from None
                if self._has_symlink_component(root_path, path_str):
                    raise ToolPermissionError(
                        f"Tool '{tool_name}' target path '{path_str}' contains a symlink component. "
                        'Symlinks are not allowed in tool call paths.',
                        reason_code=DenialReasonCode.SYMLINK_BLOCKED,
                    )
                continue

            if key not in key_set:
                continue
            if not isinstance(raw, str) or not raw.strip():
                continue
            # Containment first (see note above), then symlink defense-in-depth.
            try:
                target = (root_path / raw).resolve()
                target.relative_to(root_path)
            except (ValueError, OSError):
                raise ToolPermissionError(
                    f"Tool '{tool_name}' target path '{raw}' is outside "
                    f"workspace root '{self.workspace_root}'. "
                    'Explicit workspace root must take precedence '
                    'over any saved state.',
                    reason_code=DenialReasonCode.WORKSPACE_WRITE_MODE,
                ) from None
            if self._has_symlink_component(root_path, raw):
                raise ToolPermissionError(
                    f"Tool '{tool_name}' target path '{raw}' contains a symlink component. "
                    'Symlinks are not allowed in tool call paths.',
                    reason_code=DenialReasonCode.SYMLINK_BLOCKED,
                )
