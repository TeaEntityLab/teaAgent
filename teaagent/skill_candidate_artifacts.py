"""Required artifact bundle for quarantined skill candidates (v2)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from teaagent.storage import atomic_write_text

# Five governance artifacts plus SKILL.md (Hermes-style progressive disclosure).
REQUIRED_CANDIDATE_ARTIFACTS: tuple[str, ...] = (
    'SKILL.md',
    'REFERENCE.md',
    'tool_call_contract.json',
    'cost_profile.json',
    'interaction_policy.json',
    'provenance.json',
)

_JSON_ARTIFACTS = frozenset(
    {
        'tool_call_contract.json',
        'cost_profile.json',
        'interaction_policy.json',
        'provenance.json',
    }
)


def candidate_artifact_paths(candidate_dir: Path) -> dict[str, Path]:
    return {name: candidate_dir / name for name in REQUIRED_CANDIDATE_ARTIFACTS}


def validate_candidate_artifacts(candidate_dir: Path) -> list[str]:
    """Return human-readable errors; empty list means install-ready bundle."""
    errors: list[str] = []
    for name in REQUIRED_CANDIDATE_ARTIFACTS:
        path = candidate_dir / name
        if not path.is_file():
            errors.append(f'missing required artifact: {name}')
            continue
        if name in _JSON_ARTIFACTS:
            try:
                json.loads(path.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                errors.append(f'invalid JSON in {name}')
    return errors


def write_candidate_artifacts(
    candidate_dir: Path,
    *,
    name: str,
    description: str,
    source_run_id: str,
    task: str,
    final_answer: str,
    created_at: str,
    source_kind: str = 'agent_run',
    content_digest: str | None = None,
) -> None:
    candidate_dir.mkdir(parents=True, exist_ok=True)
    digest = content_digest or _content_digest(task=task, final_answer=final_answer)
    atomic_write_text(
        candidate_dir / 'REFERENCE.md',
        _render_reference_markdown(
            name=name,
            description=description,
            task=task,
            final_answer=final_answer,
        ),
    )
    atomic_write_text(
        candidate_dir / 'tool_call_contract.json',
        json.dumps(
            {
                'schema_version': 1,
                'skill_name': name,
                'allowed_toolsets': ['read-only'],
                'requires_approval_for': ['write', 'shell', 'network'],
            },
            indent=2,
        )
        + '\n',
    )
    atomic_write_text(
        candidate_dir / 'cost_profile.json',
        json.dumps(
            {
                'schema_version': 1,
                'skill_name': name,
                'max_prompt_tokens': 4096,
                'profile': 'conservative',
            },
            indent=2,
        )
        + '\n',
    )
    atomic_write_text(
        candidate_dir / 'interaction_policy.json',
        json.dumps(
            {
                'schema_version': 1,
                'skill_name': name,
                'trust_level': 'quarantine',
                'auto_invoke': False,
                'user_visible_rationale_required': True,
            },
            indent=2,
        )
        + '\n',
    )
    atomic_write_text(
        candidate_dir / 'provenance.json',
        json.dumps(
            {
                'schema_version': 1,
                'source_run_id': source_run_id,
                'source_kind': source_kind,
                'source_task': task.strip(),
                'created_at': created_at,
                'content_digest': digest,
                'trust_level': 'quarantine',
            },
            indent=2,
        )
        + '\n',
    )


def install_artifact_bundle(
    candidate_dir: Path,
    dest_dir: Path,
    *,
    skill_md_text: Optional[str] = None,
) -> list[str]:
    """Copy the validated bundle into an active skill directory. Returns installed paths."""
    errors = validate_candidate_artifacts(candidate_dir)
    if errors:
        raise ValueError('; '.join(errors))
    dest_dir.mkdir(parents=True, exist_ok=True)
    installed: list[str] = []
    for name in REQUIRED_CANDIDATE_ARTIFACTS:
        src = candidate_dir / name
        if name == 'SKILL.md' and skill_md_text is not None:
            atomic_write_text(dest_dir / name, skill_md_text)
        else:
            atomic_write_text(dest_dir / name, src.read_text(encoding='utf-8'))
        installed.append(str(dest_dir / name))
    return installed


def _content_digest(*, task: str, final_answer: str) -> str:
    payload = json.dumps(
        {'task': task.strip(), 'final_answer': final_answer.strip()},
        sort_keys=True,
        ensure_ascii=False,
    )
    digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    return f'sha256:{digest}'


def _render_reference_markdown(
    *, name: str, description: str, task: str, final_answer: str
) -> str:
    return (
        f'# {name}\n\n'
        f'{description.strip()}\n\n'
        '## Source task\n\n'
        f'{task.strip()}\n\n'
        '## Detailed instructions\n\n'
        f'{final_answer.strip()}\n'
    )
