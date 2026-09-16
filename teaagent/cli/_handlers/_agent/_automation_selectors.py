from __future__ import annotations

from teaagent.automations import AutomationStore


class _AmbiguousAutomationName(ValueError):
    """Raised when an automation name matches more than one stored id."""

    def __init__(self, name: str, ids: list[str]) -> None:
        self.name = name
        self.ids = list(ids)
        super().__init__(
            f'ambiguous automation name {name!r}: ids {", ".join(sorted(self.ids))}'
        )


def _resolve_selector(selector: str, entries: list[tuple[str, str]]) -> str:
    """Resolve an id or unique name to its id from ``(id, name)`` entries.

    Exact id wins; unique name match used; >1 raises ``_AmbiguousAutomationName``;
    no match returns the selector unchanged for the caller's not-found error.
    """
    if any(automation_id == selector for automation_id, _ in entries):
        return selector
    matches = [automation_id for automation_id, name in entries if name == selector]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise _AmbiguousAutomationName(selector, matches)
    return selector


def _resolve_automation_selector(store: AutomationStore, selector: str) -> str:
    """Resolve an active automation id or unique name to its stored id."""
    return _resolve_selector(
        selector, [(s.automation_id, s.name) for s in store.list()]
    )


def _resolve_quarantined_selector(store: AutomationStore, selector: str) -> str:
    """Resolve a quarantined automation id or unique name to its id."""
    return _resolve_selector(
        selector,
        [
            (row['automation_id'], row.get('name', ''))
            for row in store.list_quarantined()
        ],
    )
