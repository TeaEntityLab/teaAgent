"""Loader for skill-owned LLM prompt templates (ADR-0041 Phase 2).

Behavior-preserving harness thinning: the substantive LLM prompt reasoning for
the domain modules (task classification / workflow planning in
``coordinator.py``; agent-prompt generation / evolution in ``agent_factory.py``)
lives in reviewed skill assets under ``teaagent/skills/builtin/<skill>/`` rather
than inline in Python. Callers ``str.format(**kwargs)`` the returned template.

The deterministic fallbacks in the domain modules are unchanged: callers load
templates inside their existing ``try`` blocks, so a missing or unreadable asset
degrades through the same path as an unavailable LLM (heuristic / template
fallback) rather than crashing. Tests assert the packaged assets load and render
byte-identically to the prior inline prompts.
"""

from __future__ import annotations

import importlib.resources as resources
from functools import lru_cache

_BUILTIN_SKILLS_ANCHOR = 'teaagent'
_BUILTIN_SKILLS_SUBPATH = ('skills', 'builtin')


class PromptAssetError(RuntimeError):
    """Raised when a skill-owned prompt template asset cannot be loaded."""


@lru_cache(maxsize=None)
def load_prompt_template(skill: str, name: str) -> str:
    """Return the text of a skill-owned prompt template.

    Args:
        skill: builtin skill directory name (e.g. ``'task-classification'``).
        name: template file within the skill (e.g. ``'classification_prompt.md'``).

    Returns:
        The raw template text, suitable for ``str.format(**kwargs)``.

    Raises:
        PromptAssetError: if the asset is missing or unreadable.
    """
    rel = '/'.join((*_BUILTIN_SKILLS_SUBPATH, skill, name))
    try:
        resource = resources.files(_BUILTIN_SKILLS_ANCHOR)
        for part in (*_BUILTIN_SKILLS_SUBPATH, skill, name):
            resource = resource.joinpath(part)
        if not resource.is_file():
            raise PromptAssetError(f'prompt template not found: {rel}')
        return resource.read_text(encoding='utf-8')
    except PromptAssetError:
        raise
    except OSError as exc:
        raise PromptAssetError(f'failed to read prompt template {rel}: {exc}') from exc
