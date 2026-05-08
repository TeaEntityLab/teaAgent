from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class IntentScore:
    intent: float
    outcome: float
    scope: float
    constraints: float
    success: float


@dataclass(frozen=True)
class ClarificationResult:
    task: str
    ambiguity: float
    scores: IntentScore
    missing: tuple[str, ...]
    question: Optional[str]

    @property
    def needs_clarification(self) -> bool:
        return self.ambiguity > 0.4

    def to_dict(self) -> dict:
        return {
            'task': self.task,
            'ambiguity': self.ambiguity,
            'scores': {
                'intent': round(self.scores.intent, 3),
                'outcome': round(self.scores.outcome, 3),
                'scope': round(self.scores.scope, 3),
                'constraints': round(self.scores.constraints, 3),
                'success': round(self.scores.success, 3),
            },
            'missing': list(self.missing),
            'needs_clarification': self.needs_clarification,
            'question': self.question,
        }


ACTION_WORDS = {
    'add',
    'build',
    'change',
    'check',
    'create',
    'debug',
    'explain',
    'fix',
    'implement',
    'inspect',
    'list',
    'refactor',
    'review',
    'run',
    'search',
    'summarize',
    'test',
    'update',
}

VAGUE_WORDS = {'better', 'improve', 'optimize', 'stuff', 'thing', 'whatever', 'etc'}


def clarify_task(task: str) -> ClarificationResult:
    normalized = task.strip()
    lower = normalized.lower()
    tokens = set(re.findall(r'[a-zA-Z0-9_./-]+', lower))
    has_action = bool(tokens & ACTION_WORDS)
    has_object = len(tokens) >= 4 or any(
        marker in lower
        for marker in ('file', 'repo', 'test', 'cli', 'tui', 'api', '.py', '.md')
    )
    has_scope = any(
        marker in lower
        for marker in (
            ' in ',
            ' under ',
            'src/',
            'tests/',
            '.py',
            '.md',
            'repo',
            'project',
            'workspace',
        )
    )
    has_constraints = any(
        marker in lower
        for marker in (
            'without',
            'only',
            'must',
            'do not',
            "don't",
            'avoid',
            'keep',
            'no ',
        )
    )
    has_success = any(
        marker in lower
        for marker in (
            'pass',
            'done',
            'success',
            'verify',
            'test',
            'expected',
            'should',
        )
    )
    vague_penalty = 0.25 if tokens & VAGUE_WORDS else 0.0

    scores = IntentScore(
        intent=clamp((1.0 if has_action else 0.35) - vague_penalty),
        outcome=clamp((0.85 if has_object else 0.3) - vague_penalty),
        scope=0.85 if has_scope else 0.25,
        constraints=0.8 if has_constraints else 0.35,
        success=0.85 if has_success else 0.3,
    )
    ambiguity = round(
        1
        - (
            scores.intent * 0.30
            + scores.outcome * 0.25
            + scores.scope * 0.20
            + scores.constraints * 0.15
            + scores.success * 0.10
        ),
        3,
    )
    missing = tuple(
        name
        for name, present in (
            ('intent', has_action),
            ('outcome', has_object),
            ('scope', has_scope),
            ('constraints', has_constraints),
            ('success', has_success),
        )
        if not present
    )
    return ClarificationResult(
        task=normalized,
        ambiguity=ambiguity,
        scores=scores,
        missing=missing,
        question=next_question(missing),
    )


def build_task_spec(task: str, clarification: ClarificationResult) -> str:
    return '\n'.join(
        [
            'Clarified task specification:',
            f'TASK: {task}',
            f'AMBIGUITY: {clarification.ambiguity}',
            f'MISSING: {", ".join(clarification.missing) if clarification.missing else "none"}',
            'Proceed conservatively and ask for final clarification if required details are still missing.',
        ]
    )


def next_question(missing: tuple[str, ...]) -> Optional[str]:
    if not missing:
        return None
    first = missing[0]
    questions = {
        'intent': 'What action do you want TeaAgent to take?',
        'outcome': 'What concrete output or change should exist when this is done?',
        'scope': 'Which files, directory, or project area should this apply to?',
        'constraints': 'Are there constraints TeaAgent must follow, such as no destructive changes or preserving APIs?',
        'success': 'How should TeaAgent verify that the task succeeded?',
    }
    return questions[first]


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
