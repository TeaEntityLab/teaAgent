from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from teaagent.provenance_gate import (
    PersistenceSubstrate,
    ProvenanceSourceKind,
    evaluate_persistent_write,
)
from teaagent.run_store import RunStore
from teaagent.skill_candidate_artifacts import (
    install_artifact_bundle,
    validate_candidate_artifacts,
    write_candidate_artifacts,
)
from teaagent.skill_eval import load_eval_report, run_offline_eval, write_eval_report
from teaagent.skill_eval_dataset import write_default_eval_dataset
from teaagent.skill_review import review_skill
from teaagent.storage import atomic_write_text


@dataclass(frozen=True)
class SkillCandidate:
    candidate_id: str
    name: str
    description: str
    status: str
    created_at: str
    updated_at: str
    source_run_id: Optional[str] = None
    review_summary: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SkillCandidateStore:
    def __init__(self, root: str | Path = '.') -> None:
        self.root = Path(root).resolve()
        self.dir = self.root / '.teaagent' / 'skill-candidates'
        self.dir.mkdir(parents=True, exist_ok=True)

    def _dir(self, candidate_id: str) -> Path:
        return self.dir / candidate_id

    def _meta(self, candidate_id: str) -> Path:
        return self._dir(candidate_id) / 'candidate.json'

    def _skill(self, candidate_id: str) -> Path:
        return self._dir(candidate_id) / 'SKILL.md'

    def list(self) -> list[SkillCandidate]:
        rows: list[SkillCandidate] = []
        for path in sorted(self.dir.glob('*/candidate.json')):
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                continue
            rows.append(SkillCandidate(**payload))
        return sorted(rows, key=lambda r: r.created_at, reverse=True)

    def show(self, candidate_id: str) -> SkillCandidate:
        meta = self._meta(candidate_id)
        if not meta.exists():
            raise FileNotFoundError(f"skill candidate '{candidate_id}' not found")
        payload = json.loads(meta.read_text(encoding='utf-8'))
        return SkillCandidate(**payload)

    def skill_path(self, candidate_id: str) -> Path:
        return self._skill(candidate_id)

    def candidate_dir(self, candidate_id: str) -> Path:
        return self._dir(candidate_id)

    def create_from_run(
        self, *, run_id: str, name: str, description: str
    ) -> SkillCandidate:
        run_store = RunStore(self.root)
        task = run_store.task_for_run(run_id)
        events = run_store.show_run(run_id)
        final_answer = ''
        for event in reversed(events):
            if event.get('event_type') == 'run_completed':
                answer = event.get('payload', {}).get('answer')
                if isinstance(answer, str):
                    final_answer = answer
                break
        if not final_answer:
            raise ValueError('run has no completed final answer; cannot propose skill')
        candidate_id = uuid4().hex
        from teaagent.audit import utc_now

        now = utc_now()
        candidate = SkillCandidate(
            candidate_id=candidate_id,
            name=name.strip(),
            description=description.strip(),
            status='proposed',
            created_at=now,
            updated_at=now,
            source_run_id=run_id,
        )
        target_dir = self._dir(candidate_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        skill_text = _render_skill_markdown(
            name=name.strip(),
            description=description.strip(),
            task=task,
            final_answer=final_answer,
        )
        atomic_write_text(self._skill(candidate_id), skill_text)
        gate = evaluate_persistent_write(
            substrate=PersistenceSubstrate.SKILL_CANDIDATE,
            payload={
                'name': name.strip(),
                'description': description.strip(),
                'task': task,
            },
            source_kind=ProvenanceSourceKind.AGENT_RUN,
        )
        write_candidate_artifacts(
            target_dir,
            name=name.strip(),
            description=description.strip(),
            source_run_id=run_id,
            task=task,
            final_answer=final_answer,
            created_at=now,
            source_kind=gate.source_kind.value,
            content_digest=gate.content_digest,
        )
        write_default_eval_dataset(
            target_dir,
            task=task,
            final_answer=final_answer,
            skill_name=name.strip(),
        )
        atomic_write_text(self._meta(candidate_id), json.dumps(candidate.to_dict()))
        return self.run_offline_eval(candidate_id)

    def run_offline_eval(self, candidate_id: str) -> SkillCandidate:
        candidate_dir = self._dir(candidate_id)
        report = run_offline_eval(candidate_dir)
        write_eval_report(candidate_dir, report)
        if report.passed:
            return self.show(candidate_id)
        summary = '; '.join(report.failures[:3]) or 'offline eval failed'
        return self.set_review(candidate_id, status='eval_failed', summary=summary)

    def set_review(
        self, candidate_id: str, *, status: str, summary: str
    ) -> SkillCandidate:
        current = self.show(candidate_id)
        from teaagent.audit import utc_now

        updated = SkillCandidate(
            **{
                **current.to_dict(),
                'status': status,
                'review_summary': summary,
                'updated_at': utc_now(),
            }
        )
        atomic_write_text(self._meta(candidate_id), json.dumps(updated.to_dict()))
        return updated

    def review(self, candidate_id: str) -> SkillCandidate:
        candidate_dir = self._dir(candidate_id)
        eval_report = load_eval_report(candidate_dir)
        if eval_report is None or not eval_report.passed:
            refreshed = self.run_offline_eval(candidate_id)
            eval_report = load_eval_report(candidate_dir)
            if eval_report is None or not eval_report.passed:
                return refreshed
        artifact_errors = validate_candidate_artifacts(candidate_dir)
        if artifact_errors:
            summary = '; '.join(artifact_errors[:3])
            return self.set_review(
                candidate_id, status='review_failed', summary=summary
            )
        skill_path = self.skill_path(candidate_id)
        result = review_skill(skill_path)
        errors = [
            finding.message
            for finding in result.findings
            if finding.severity == 'error'
        ]
        warnings = [
            finding.message
            for finding in result.findings
            if finding.severity == 'warning'
        ]
        if errors:
            summary = '; '.join(errors[:3])
            return self.set_review(
                candidate_id, status='review_failed', summary=summary
            )
        summary = 'passed'
        if warnings:
            summary = f'passed_with_warnings: {"; ".join(warnings[:3])}'
        return self.set_review(candidate_id, status='review_passed', summary=summary)

    def install(self, candidate_id: str, *, scope: str) -> dict[str, Any]:
        candidate = self.show(candidate_id)
        if candidate.status not in {'review_passed', 'installed'}:
            raise ValueError('candidate must pass review before install')
        eval_report = load_eval_report(self._dir(candidate_id))
        if eval_report is None or not eval_report.passed:
            raise ValueError('candidate must pass offline eval before install')
        candidate_dir = self._dir(candidate_id)
        artifact_errors = validate_candidate_artifacts(candidate_dir)
        if artifact_errors:
            raise ValueError('; '.join(artifact_errors))
        src = self.skill_path(candidate_id)
        if scope == 'project':
            dest_dir = self.root / '.config' / 'agent' / 'skills' / candidate.name
        elif scope == 'personal':
            dest_dir = Path.home() / '.config' / 'agent' / 'skills' / candidate.name
        else:
            raise ValueError("scope must be 'project' or 'personal'")
        installed_paths = install_artifact_bundle(
            candidate_dir,
            dest_dir,
            skill_md_text=src.read_text(encoding='utf-8'),
        )
        dest = dest_dir / 'SKILL.md'
        updated = self.set_review(
            candidate_id, status='installed', summary=f'installed:{scope}:{dest}'
        )
        return {
            'candidate': updated.to_dict(),
            'installed_path': str(dest),
            'installed_paths': installed_paths,
        }


def _render_skill_markdown(
    *, name: str, description: str, task: str, final_answer: str
) -> str:
    return (
        '---\n'
        f'name: {name}\n'
        f'description: {description}\n'
        '---\n\n'
        '# Context\n'
        f'- Source task: {task.strip()}\n\n'
        '# Instructions\n'
        f'{final_answer.strip()}\n'
    )
