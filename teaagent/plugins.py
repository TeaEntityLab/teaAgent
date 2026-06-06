"""Plugin loader via Python entry-points (backward-compatible re-export).

This module is a thin re-export of the unified plugin system in
:mod:`teaagent.plugin_system`.  All plugin loading logic now lives there;
this module exists only for backward compatibility.

Usage::

    from teaagent.plugins import load_plugins
    from teaagent.tools import ToolRegistry

    registry = ToolRegistry()
    result = load_plugins(registry)
    if not result.ok:
        print("Failed plugins:", result.failed)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from teaagent.plugin_system import (
    PLUGIN_GROUP,
    PluginLoadResult,  # noqa: F401 — re-export for backward compat
    _audit_plugin_source,  # noqa: F401 — re-export for backward compat (tests patch it here)
    _entry_points,
    load_entry_point_tools,
)

if TYPE_CHECKING:
    from teaagent.tools import ToolRegistry


def load_plugins(
    registry: ToolRegistry, *, group: str = PLUGIN_GROUP
) -> PluginLoadResult:
    """Backward-compatible wrapper for :func:`~teaagent.plugin_system.load_entry_point_tools`.

    Passes this module's ``_entry_points`` so tests can monkeypatch
    ``teaagent.plugins._entry_points``.
    """
    return load_entry_point_tools(registry, group=group, _ep_loader=_entry_points)
