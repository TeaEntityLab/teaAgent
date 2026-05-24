"""Required artifact bundle for quarantined skill candidates (v2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from teaagent.provenance_gate import (
    PersistenceSubstrate,
    canonical_content_digest,
)
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
    parsed: dict[str, object] = {}
    for name in REQUIRED_CANDIDATE_ARTIFACTS:
        path = candidate_dir / name
        if not path.is_file():
            errors.append(f'missing required artifact: {name}')
            continue
        if name in _JSON_ARTIFACTS:
            try:
                parsed[name] = json.loads(path.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                errors.append(f'invalid JSON in {name}')
    if errors:
        return errors
    errors.extend(_validate_tool_call_contract(parsed.get('tool_call_contract.json')))
    errors.extend(_validate_cost_profile(parsed.get('cost_profile.json')))
    errors.extend(_validate_interaction_policy(parsed.get('interaction_policy.json')))
    errors.extend(_validate_provenance(candidate_dir, parsed.get('provenance.json')))
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
    reference_text = _render_reference_markdown(
        name=name,
        description=description,
        task=task,
        final_answer=final_answer,
    )
    tool_call_contract = {
        'schema_version': 1,
        'skill_name': name,
        'allowed_toolsets': ['read-only'],
        'requires_approval_for': ['write', 'shell', 'network'],
    }
    cost_profile = {
        'schema_version': 1,
        'skill_name': name,
        'max_prompt_tokens': 4096,
        'profile': 'conservative',
    }
    interaction_policy = {
        'schema_version': 1,
        'skill_name': name,
        'trust_level': 'quarantine',
        'auto_invoke': False,
        'user_visible_rationale_required': True,
    }
    atomic_write_text(
        candidate_dir / 'REFERENCE.md',
        reference_text,
    )
    atomic_write_text(
        candidate_dir / 'tool_call_contract.json',
        json.dumps(tool_call_contract, indent=2) + '\n',
    )
    atomic_write_text(
        candidate_dir / 'cost_profile.json',
        json.dumps(cost_profile, indent=2) + '\n',
    )
    atomic_write_text(
        candidate_dir / 'interaction_policy.json',
        json.dumps(interaction_policy, indent=2) + '\n',
    )
    digest = candidate_bundle_digest(candidate_dir)
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
                'gate_content_digest': content_digest or '',
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


def candidate_bundle_digest(candidate_dir: Path) -> str:
    payload: dict[str, object] = {'schema_version': 1}
    for name in REQUIRED_CANDIDATE_ARTIFACTS:
        if name == 'provenance.json':
            continue
        path = candidate_dir / name
        if not path.is_file():
            payload[name] = None
            continue
        text = path.read_text(encoding='utf-8')
        if name in _JSON_ARTIFACTS:
            try:
                payload[name] = json.loads(text)
            except json.JSONDecodeError:
                payload[name] = text
        else:
            payload[name] = text
    return canonical_content_digest(
        substrate=PersistenceSubstrate.SKILL_CANDIDATE,
        payload=payload,
    )


def _validate_tool_call_contract(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ['tool_call_contract.json must contain a JSON object']
    errors: list[str] = []
    allowed = payload.get('allowed_toolsets')
    if not isinstance(allowed, list) or not all(
        isinstance(item, str) for item in allowed
    ):
        errors.append('tool_call_contract.json allowed_toolsets must be a string list')
    elif set(allowed) - {'read-only'}:
        errors.append('tool_call_contract.json may only grant read-only by default')
    required_approval = payload.get('requires_approval_for')
    required = {'write', 'shell', 'network'}
    if not isinstance(required_approval, list) or not required.issubset(
        {str(item) for item in required_approval}
    ):
        errors.append(
            'tool_call_contract.json must require approval for write, shell, and network'
        )
    return errors


def _validate_cost_profile(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ['cost_profile.json must contain a JSON object']
    value = payload.get('max_prompt_tokens')
    if not isinstance(value, int) or value <= 0 or value > 8192:
        return ['cost_profile.json max_prompt_tokens must be between 1 and 8192']
    return []


def _validate_interaction_policy(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ['interaction_policy.json must contain a JSON object']
    errors: list[str] = []
    if payload.get('trust_level') != 'quarantine':
        errors.append('interaction_policy.json trust_level must be quarantine')
    if payload.get('auto_invoke') is not False:
        errors.append('interaction_policy.json auto_invoke must be false')
    if payload.get('user_visible_rationale_required') is not True:
        errors.append(
            'interaction_policy.json user_visible_rationale_required must be true'
        )
    return errors


def _validate_provenance(candidate_dir: Path, payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ['provenance.json must contain a JSON object']
    errors: list[str] = []
    if payload.get('trust_level') != 'quarantine':
        errors.append('provenance.json trust_level must be quarantine')
    digest = str(payload.get('content_digest', '')).strip()
    expected = candidate_bundle_digest(candidate_dir)
    if digest != expected:
        errors.append(
            'provenance.json content_digest does not match candidate bundle; rerun eval'
        )
    return errors


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
