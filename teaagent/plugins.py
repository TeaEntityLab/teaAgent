"""Plugin loader via Python entry-points.

Third-party packages register workspace tools by adding an entry-point in
their ``pyproject.toml``::

    [project.entry-points."teaagent.tools"]
    my_tools = "my_package.tools:register"

The entry-point value must be a callable with the signature::

    def register(registry: ToolRegistry) -> None: ...

It is called once during :func:`load_plugins` and may register any number
of tools via ``ToolRegistry.register``.

Usage::

    from teaagent.plugins import load_plugins
    from teaagent.tools import ToolRegistry

    registry = ToolRegistry()
    result = load_plugins(registry)
    if not result.ok:
        print("Failed plugins:", result.failed)
"""

from __future__ import annotations

import importlib.metadata
import sys
from dataclasses import dataclass, field
from typing import Any

from teaagent.tools import ToolRegistry

PLUGIN_GROUP = 'teaagent.tools'


@dataclass(frozen=True)
class PluginLoadResult:
    """Summary of a :func:`load_plugins` call."""

    loaded: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.failed) == 0


def _entry_points(group: str) -> list[Any]:
    """Thin wrapper so tests can patch without touching importlib.metadata."""
    try:
        eps = importlib.metadata.entry_points()
        if sys.version_info >= (3, 12):
            return list(eps.select(group=group))
        return list(eps.get(group, []))
    except Exception:
        return []


def load_plugins(
    registry: ToolRegistry,
    *,
    group: str = PLUGIN_GROUP,
) -> PluginLoadResult:
    """Discover and load all installed plugins for *group*.

    Each entry-point is loaded and called with *registry*.  Any exception
    raised during loading or registration is caught, the plugin name is
    added to :attr:`PluginLoadResult.failed`, and processing continues
    with the next plugin.

    Parameters
    ----------
    registry:
        The :class:`~teaagent.tools.ToolRegistry` that plugins should
        register their tools into.
    group:
        Entry-point group name to scan (default: ``"teaagent.tools"``).

    Returns
    -------
    :class:`PluginLoadResult`
        Lists of successfully loaded and failed plugin names.
    """
    loaded: list[str] = []
    failed: list[str] = []

    for ep in _entry_points(group):
        name = getattr(ep, 'name', str(ep))
        try:
            fn = ep.load()
            fn(registry)
            loaded.append(name)
        except Exception:
            failed.append(name)

    return PluginLoadResult(loaded=loaded, failed=failed)
