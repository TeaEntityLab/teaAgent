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
