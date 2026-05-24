from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from teaagent.run_store import RunStore
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
        atomic_write_text(self._meta(candidate_id), json.dumps(candidate.to_dict()))
        return candidate

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
        src = self.skill_path(candidate_id)
        if scope == 'project':
            dest_dir = self.root / '.config' / 'agent' / 'skills' / candidate.name
        elif scope == 'personal':
            dest_dir = Path.home() / '.config' / 'agent' / 'skills' / candidate.name
        else:
            raise ValueError("scope must be 'project' or 'personal'")
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / 'SKILL.md'
        atomic_write_text(dest, src.read_text(encoding='utf-8'))
        updated = self.set_review(
            candidate_id, status='installed', summary=f'installed:{scope}:{dest}'
        )
        return {'candidate': updated.to_dict(), 'installed_path': str(dest)}


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
