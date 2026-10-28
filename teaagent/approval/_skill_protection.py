"""Protected active-skill directory checks (DSK-P0-002).

Moved unchanged from ``teaagent.approval.manager`` (A-P1-6 split, ADR-0044).
``teaagent.approval.manager`` re-exports the public and private names. The
method ``ApprovalManager._assert_skill_path_not_protected`` stays in that module
so that patches on ``teaagent.approval.manager._is_skill_dev_opt_in`` still apply.
"""

from __future__ import annotations

import os
from pathlib import Path

_PROTECTED_SKILL_PATTERNS = (
    '.config/agent/skills',
    '.claude/skills',
    '.opencode/skill',
    '.opencode/skills',
)


_CANDIDATE_SKILL_PREFIX = '.teaagent/skill-candidates'


def is_protected_skill_path(workspace_root: Path, target_path: Path) -> bool:
    """Return True if *target_path* resides under a protected active-skill directory.

    Protected directories match one of the ``_PROTECTED_SKILL_PATTERNS``
    relative to *workspace_root*.  The candidate install path
    ``.teaagent/skill-candidates/`` is explicitly excluded so proposals
    continue to work.
    """
    try:
        relative = target_path.resolve().relative_to(workspace_root.resolve())
    except ValueError:
        # Outside the workspace: not a protected skill directory.
        return False
    except OSError:
        # Fail closed (owner decision 2026-10-27, approval split-plan Q6, F5):
        # a path that cannot be resolved cannot be shown to be unprotected.
        return True

    relative_str = str(relative)

    # Candidate path is always allowed.
    if (
        relative_str.startswith(_CANDIDATE_SKILL_PREFIX + '/')
        or relative_str == _CANDIDATE_SKILL_PREFIX
    ):
        return False

    for pattern in _PROTECTED_SKILL_PATTERNS:
        pattern_prefix = pattern + '/'
        if relative_str.startswith(pattern_prefix) or relative_str == pattern:
            return True

    return False


def _is_skill_dev_opt_in(workspace_root: str | Path) -> bool:
    """Check whether the skill-dev opt-in is active.

    Returns True when either the ``TEAAGENT_SKILL_DEV_OPT_IN`` environment
    variable is set to a truthy value, or the ``skill_dev_opt_in`` key is
    set to ``true`` in the workspace config (``.teaagent/config.json``).
    """
    env_val = os.environ.get('TEAAGENT_SKILL_DEV_OPT_IN')
    if env_val is not None:
        return env_val.strip().lower() in {'1', 'true', 'yes'}

    from teaagent.config_loader import load_workspace_config

    cfg = load_workspace_config(workspace_root)
    return bool(cfg.get('skill_dev_opt_in', False))
