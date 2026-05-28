from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from teaagent.skill_loader import load_skills_with_report
from teaagent.skill_review import SkillReviewResult, review_skill


@dataclass(frozen=True)
class SkillDraft:
    name: str
    description: str
    skill_md: str
    tool_code: str


@dataclass(frozen=True)
class SkillWriterResult:
    ok: bool
    skill_dir: Optional[Path] = None
    message: str = ''
    review: Optional[SkillReviewResult] = None


class SkillWriter:
    """Draft, validate, and publish skill packages."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._skills_dir = self._root / '.config' / 'agent' / 'skills'

    def draft(self, objective: str, *, name: str = 'generated_skill') -> SkillDraft:
        safe_name = name.strip().replace(' ', '_')
        skill_md = (
            '---\n'
            f'name: {safe_name}\n'
            f'description: {objective}\n'
            '---\n\n'
            f'# {safe_name}\n\n'
            f'{objective}\n'
        )
        tool_code = (
            'from __future__ import annotations\n\n'
            'def run(payload: dict[str, object]) -> dict[str, object]:\n'
            '    return {"ok": True, "payload": payload}\n'
        )
        return SkillDraft(
            name=safe_name,
            description=objective,
            skill_md=skill_md,
            tool_code=tool_code,
        )

    def static_validate(self, draft: SkillDraft) -> SkillReviewResult:
        temp_dir = self._skills_dir / draft.name
        temp_dir.mkdir(parents=True, exist_ok=True)
        (temp_dir / 'SKILL.md').write_text(draft.skill_md, encoding='utf-8')
        (temp_dir / 'tool.py').write_text(draft.tool_code, encoding='utf-8')
        return review_skill(temp_dir)

    def publish(self, draft: SkillDraft) -> SkillWriterResult:
        skill_dir = self._skills_dir / draft.name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / 'SKILL.md').write_text(draft.skill_md, encoding='utf-8')
        (skill_dir / 'tool.py').write_text(draft.tool_code, encoding='utf-8')

        review = review_skill(skill_dir)
        dangerous_findings = [
            finding
            for finding in review.findings
            if 'dangerous' in finding.message.lower()
        ]
        if not review.passed or dangerous_findings:
            return SkillWriterResult(
                ok=False,
                skill_dir=skill_dir,
                message='skill review failed',
                review=review,
            )

        report = load_skills_with_report(
            self._root, preferred_dirs=['.config/agent/skills']
        )
        loaded_names = {skill.name for skill in report.skills}
        if draft.name not in loaded_names:
            return SkillWriterResult(
                ok=False,
                skill_dir=skill_dir,
                message='skill published but not discovered by loader',
                review=review,
            )
        return SkillWriterResult(
            ok=True,
            skill_dir=skill_dir,
            message='skill published and discoverable',
            review=review,
        )

    def publish_from_dict(self, payload: dict[str, Any]) -> SkillWriterResult:
        draft = SkillDraft(
            name=str(payload.get('name', 'generated_skill')),
            description=str(payload.get('description', 'Generated skill')),
            skill_md=str(payload.get('skill_md', '')),
            tool_code=str(payload.get('tool_code', '')),
        )
        return self.publish(draft)
