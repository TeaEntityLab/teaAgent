from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Literal

from teaagent.skill_candidates import SkillCandidateStore
from teaagent.skill_lifecycle import SkillLifecycleState, SkillLifecycleTracker
from teaagent.skill_loader import explain_skill_activation


def _print_json(value: Any) -> None:
    import json

    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def skill_explain_command(args: argparse.Namespace) -> int:
    prompt_mode: Literal['eager', 'index_only'] = (
        'index_only' if getattr(args, 'skill_index_only', False) else 'eager'
    )
    if getattr(args, 'no_auto_skills', False) or getattr(
        args, 'skill_index_only', False
    ):
        selected: frozenset[str] | None = frozenset()
    else:
        names = [
            str(item).strip()
            for item in (getattr(args, 'skill', None) or [])
            if str(item).strip()
        ]
        selected = frozenset(names) if names else None
    report = explain_skill_activation(
        args.root,
        selected_names=selected,
        skill_prompt_mode=prompt_mode,
    )
    _print_json({'status': 'ok', 'activation': report.to_dict()})
    return 0


def skill_activate_command(args: argparse.Namespace) -> int:
    names: list[str] = [
        str(item).strip()
        for item in (getattr(args, 'name', None) or [])
        if str(item).strip()
    ]
    root = str(args.root)

    # Validate each skill exists (bypass activated-skills union to catch typos)
    from teaagent.skill_loader import load_skills_with_report

    for name in names:
        report = load_skills_with_report(
            root,
            selected_names=frozenset({name}),
        )
        skill_names = [s.name for s in report.skills]
        if name not in skill_names:
            _print_json({'status': 'error', 'message': f'skill not found: {name}'})
            return 1

    # Write activation config file
    dot_teaagent = Path(root) / '.teaagent'
    dot_teaagent.mkdir(parents=True, exist_ok=True)
    config_path = dot_teaagent / 'activated-skills.json'

    activated: list[str] = []
    if config_path.is_file():
        try:
            existing = json.loads(config_path.read_text(encoding='utf-8'))
            if isinstance(existing, dict):
                activated = existing.get('activated_skills', [])
        except (OSError, json.JSONDecodeError):
            pass

    for name in names:
        if name not in activated:
            activated.append(name)

    config_path.write_text(
        json.dumps({'activated_skills': activated}, indent=2) + '\n',
        encoding='utf-8',
    )

    # Record audit events
    tracker = SkillLifecycleTracker(run_id='cli_activate')
    for name in names:
        tracker.transition(
            name,
            SkillLifecycleState.ACTIVATED.value,
            reason='explicitly activated via CLI (activate_skill)',
        )

    _print_json({'status': 'activated', 'skill': names if len(names) > 1 else names[0]})
    return 0


def skill_candidate_propose_command(args: argparse.Namespace) -> int:
    store = SkillCandidateStore(args.root)
    try:
        row = store.create_from_run(
            run_id=args.from_run,
            name=args.name,
            description=args.description,
        )
    except (FileNotFoundError, ValueError) as exc:
        _print_json({'status': 'error', 'message': str(exc)})
        return 1
    from teaagent.skill_eval import load_eval_report

    eval_report = load_eval_report(store.candidate_dir(row.candidate_id))
    status = 'proposed' if row.status == 'proposed' else 'eval_failed'
    payload: dict[str, object] = {'status': status, 'candidate': row.to_dict()}
    if eval_report is not None:
        payload['eval'] = eval_report.to_dict()
    _print_json(payload)
    return 0 if status == 'proposed' else 2


def skill_candidate_eval_command(args: argparse.Namespace) -> int:
    store = SkillCandidateStore(args.root)
    try:
        row = store.run_offline_eval(args.candidate_id)
    except FileNotFoundError as exc:
        _print_json({'status': 'error', 'message': str(exc)})
        return 1
    from teaagent.skill_eval import load_eval_report

    eval_report = load_eval_report(store.candidate_dir(args.candidate_id))
    passed = bool(eval_report and eval_report.passed)
    _print_json(
        {
            'status': 'eval_passed' if passed else 'eval_failed',
            'candidate': row.to_dict(),
            'eval': eval_report.to_dict() if eval_report else {},
        }
    )
    return 0 if passed else 2


def skill_candidate_list_command(args: argparse.Namespace) -> int:
    rows = [
        row.to_dict() for row in SkillCandidateStore(args.root, readonly=True).list()
    ]
    _print_json(rows)
    return 0


def skill_candidate_show_command(args: argparse.Namespace) -> int:
    store = SkillCandidateStore(args.root, readonly=True)
    try:
        row = store.show(args.candidate_id)
    except FileNotFoundError as exc:
        _print_json({'status': 'error', 'message': str(exc)})
        return 1
    _print_json(
        {
            'candidate': row.to_dict(),
            'skill_path': str(store.skill_path(args.candidate_id)),
        }
    )
    return 0


def skill_candidate_review_command(args: argparse.Namespace) -> int:
    store = SkillCandidateStore(args.root)
    try:
        row = store.review(args.candidate_id)
    except FileNotFoundError as exc:
        _print_json({'status': 'error', 'message': str(exc)})
        return 1
    _print_json({'status': row.status, 'candidate': row.to_dict()})
    return 0


def skill_candidate_install_command(args: argparse.Namespace) -> int:
    store = SkillCandidateStore(args.root)

    approved_gate_id = getattr(args, 'approved_gate_id', None)
    attested_personal = bool(getattr(args, 'i_attest_personal_install', False))

    if approved_gate_id:
        from teaagent.governance.plan_gate import load_gate

        try:
            gate = load_gate(approved_gate_id, workspace_root=args.root)
        except FileNotFoundError:
            _print_json({'status': 'error', 'message': f'approved gate not found: {approved_gate_id}'})
            return 1
        if gate.decision != 'approved':
            _print_json(
                {
                    'status': 'error',
                    'message': f'gate {approved_gate_id} is not approved '
                    f'(current: {gate.decision})',
                }
            )
            return 1
        if not gate.approver.strip():
            _print_json(
                {
                    'status': 'error',
                    'message': f'gate {approved_gate_id} has no approver',
                }
            )
            return 1
        if gate.target_type != 'skill_install':
            _print_json(
                {
                    'status': 'error',
                    'message': f'gate {approved_gate_id} target_type is '
                    f'{gate.target_type}, expected skill_install',
                }
            )
            return 1
        if gate.target_name != getattr(args, 'candidate_id', ''):
            _print_json(
                {
                    'status': 'error',
                    'message': f'gate {approved_gate_id} target_name is '
                    f'{gate.target_name}, expected {getattr(args, "candidate_id", "")}',
                }
            )
            return 1
    else:
        candidate = store.show(args.candidate_id)
        risk_reason = (
            f'Installing skill candidate {candidate.name} '
            f'(scope={args.scope}, status={candidate.status})'
        )
        from teaagent.governance.plan_gate import require_review_gate

        gate = require_review_gate(
            target_type='skill_install',
            target_name=getattr(args, 'candidate_id', ''),
            risk_reason=risk_reason,
            workspace_root=args.root,
        )
        hint = ''
        if getattr(args, 'scope', 'project') == 'personal':
            hint = ' Use --i-attest-personal-install to attest personal scope install.'
        action_hint = f'Review then approve the gate, then retry with --approved-gate-id {gate.gate_id}'
        _print_json(
            {
                'status': 'gate_required',
                'gate': gate.to_dict(),
                'hint': (hint + ' ' + action_hint if hint else action_hint).strip(),
            }
        )
        return 1

    try:
        payload = store.install(
            args.candidate_id,
            scope=args.scope,
            attested_personal=attested_personal,
        )
    except (FileNotFoundError, ValueError) as exc:
        _print_json({'status': 'error', 'message': str(exc)})
        return 1
    _print_json({'status': 'installed', **payload})
    return 0


def skill_candidate_eval_real_command(args: argparse.Namespace) -> int:
    store = SkillCandidateStore(args.root)
    candidate_dir = store.candidate_dir(args.candidate_id)
    if not candidate_dir.is_dir():
        _print_json(
            {
                'status': 'error',
                'message': f'candidate not found: {args.candidate_id}',
            }
        )
        return 1

    model = getattr(args, 'model', 'gpt-4o')
    provider = getattr(args, 'provider', 'gpt')

    from teaagent.skill_eval_real import (
        run_real_model_eval,
        write_real_eval_report,
    )

    report = run_real_model_eval(candidate_dir, model=model, provider=provider)
    write_real_eval_report(candidate_dir, report)

    _print_json(
        {
            'status': 'ok',
            'candidate_id': args.candidate_id,
            'eval': report.to_dict(),
        }
    )
    return 0


def skill_health_command(args: argparse.Namespace) -> int:
    from pathlib import Path

    from teaagent.skill_loader import get_skill_health

    root = Path(args.root).resolve()
    health = get_skill_health(root)
    _print_json(health)
    return 0


def skill_candidate_repair_tasks_command(args: argparse.Namespace) -> int:
    store = SkillCandidateStore(args.root, readonly=True)
    candidate_dir = store.candidate_dir(args.candidate_id)
    if not candidate_dir.is_dir():
        _print_json({'status': 'error', 'message': f'candidate not found: {args.candidate_id}'})
        return 1
    from teaagent.skill_repair import load_repair_tasks

    tasks = load_repair_tasks(candidate_dir)
    _print_json({
        'status': 'ok',
        'candidate_id': args.candidate_id,
        'repair_tasks': [t.to_dict() for t in tasks],
        'total': len(tasks),
    })
    return 0 if not tasks else 1  # return 1 when there are outstanding repair tasks
