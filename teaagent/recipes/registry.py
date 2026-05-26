from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class Recipe:
    name: str
    description: str
    task_template: str
    permission_mode: str = 'read-only'
    context_profile: str = 'lean'

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'task_template': self.task_template,
            'permission_mode': self.permission_mode,
            'context_profile': self.context_profile,
        }


RECIPES: dict[str, Recipe] = {
    'first-hour': Recipe(
        name='first-hour',
        description='Golden path: setup health, daily readiness, plan, run, verify, undo',
        task_template=(
            'Walk through the TeaAgent first-hour path for this repo: confirm harness '
            'health and daily readiness, outline a minimal plan artifact, list verification '
            'commands (pytest or project tests), and note when to use `teaagent agent undo`. '
            'Do not edit files in this recipe run.'
        ),
        permission_mode='read-only',
        context_profile='lean',
    ),
    'review-staged': Recipe(
        name='review-staged',
        description='Review git staged diff for issues before commit',
        task_template='Review the git staged diff for bugs, security issues, and missing tests. Summarize findings by severity.',
        permission_mode='read-only',
    ),
    'fix-ci': Recipe(
        name='fix-ci',
        description='Diagnose failing CI from recent logs or test output',
        task_template='Analyze the latest failing CI/test output in this repo and propose minimal fixes.',
        permission_mode='workspace-write',
        context_profile='balanced',
    ),
    'docs-drift': Recipe(
        name='docs-drift',
        description='Check competitive docs drift via refresh script',
        task_template='Run scripts/refresh_competitive_docs.py --check and report any drift.',
        permission_mode='read-only',
        context_profile='lean',
    ),
    'security-pass': Recipe(
        name='security-pass',
        description='Quick security review of changed files',
        task_template='Perform a security-focused review of recently changed source files.',
        permission_mode='read-only',
    ),
    'fix-failing-test': Recipe(
        name='fix-failing-test',
        description='Diagnose and fix the current failing test with minimal diff',
        task_template=(
            'Find the failing test output in this repo, identify the root cause, '
            'and propose the smallest fix with tests passing.'
        ),
        permission_mode='workspace-write',
        context_profile='balanced',
    ),
    'summarize-repo': Recipe(
        name='summarize-repo',
        description='High-level repo summary for onboarding or stand-up',
        task_template=(
            'Summarize this repository: purpose, main packages, how to run tests, '
            'and the top three risks or gaps.'
        ),
        permission_mode='read-only',
        context_profile='lean',
    ),
    'map-architecture': Recipe(
        name='map-architecture',
        description='Map major modules and data flow',
        task_template=(
            'Map the architecture of this codebase: entry points, core modules, '
            'external integrations, and extension boundaries.'
        ),
        permission_mode='read-only',
        context_profile='deep',
    ),
    'safe-cleanup': Recipe(
        name='safe-cleanup',
        description='Suggest safe dead-code and doc cleanup without applying',
        task_template=(
            'Identify low-risk cleanup opportunities (unused imports, stale docs, '
            'duplicate helpers). Output a plan only; do not edit files.'
        ),
        permission_mode='read-only',
        context_profile='balanced',
    ),
    'write-tests': Recipe(
        name='write-tests',
        description='Add focused tests for recent changes',
        task_template=(
            'Review recent changes and add focused unit or acceptance tests '
            'for the highest-risk behavior gaps.'
        ),
        permission_mode='workspace-write',
        context_profile='balanced',
    ),
    'release-check': Recipe(
        name='release-check',
        description='Pre-release checklist: docs drift, tests, competitive gate',
        task_template=(
            'Run a release checklist: scripts/refresh_competitive_docs.py --check, '
            'note doc/provider drift, list risky diffs, and summarize blockers.'
        ),
        permission_mode='read-only',
        context_profile='lean',
    ),
}


def list_recipes() -> list[dict[str, Any]]:
    return [recipe.to_dict() for recipe in RECIPES.values()]


def run_recipe(
    name: str,
    *,
    extra: str = '',
    on_run: Optional[Callable[..., Any]] = None,
) -> dict[str, Any]:
    recipe = RECIPES.get(name)
    if not recipe:
        allowed = ', '.join(sorted(RECIPES))
        raise KeyError(f"unknown recipe '{name}'. Available: {allowed}")
    task = recipe.task_template
    if extra:
        task = f'{task}\n\nAdditional context:\n{extra}'
    payload = {
        'recipe': recipe.name,
        'task': task,
        'permission_mode': recipe.permission_mode,
        'context_profile': recipe.context_profile,
    }
    if on_run is not None:
        payload['result'] = on_run(task=task, recipe=recipe)
    return payload
