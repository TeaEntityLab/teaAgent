"""Release evidence bundle — seven-loop evidence status for release gates.

Provides ``build_release_evidence_bundle()`` and ``write_release_evidence_bundle()``
that generate a JSON bundle with platform info, git info, pytest counts,
seven-loop evidence status, gate commands, and artifact hashes.

See also: ``docs/governance/release-process.md``, ``docs/release-checklist.md``.
"""

from __future__ import annotations

import hashlib
import json
import platform
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ────────────────────────────────────────────────────────────────────────────
# Data classes
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class ReleaseEvidenceBundle:
    """Complete release evidence bundle with seven-loop status."""

    commands_ok: bool
    collection_ok: bool
    evidence_complete: bool
    created_at: str  # ISO-8601
    repo_root: str
    run_profile: str  # 'release' | 'full' | 'counts-only'

    platform: dict  # python_version, os, platform
    git: dict  # branch, commit, dirty, tags
    pytest_counts: dict  # acceptance_collected, suite_collected, ...
    seven_loop_evidence: dict  # each loop: name, status, receipts
    commands: list[dict]  # [{cmd, exit_code, duration_seconds}, ...]
    artifacts: list[dict]  # [{path, sha256, bytes}, ...]

    @property
    def ok(self) -> bool:
        """Backward-compatible overall status: all three sub-checks pass."""
        return self.commands_ok and self.collection_ok and self.evidence_complete


# ────────────────────────────────────────────────────────────────────────────
# Helper functions
# ────────────────────────────────────────────────────────────────────────────


def _sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    digest = hashlib.sha256()
    try:
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(chunk)
    except OSError:
        return ''
    return digest.hexdigest()


def _run(argv: list[str], *, cwd: Path, timeout_seconds: int = 600) -> dict[str, Any]:
    """Run a command and return result dict."""
    started = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        ended = time.monotonic()
        return {
            'cmd': ' '.join(shlex.quote(part) for part in argv),
            'exit_code': proc.returncode,
            'duration_seconds': round(ended - started, 3),
            'stdout': proc.stdout,
            'stderr': proc.stderr,
        }
    except (subprocess.TimeoutExpired, OSError) as exc:
        ended = time.monotonic()
        return {
            'cmd': ' '.join(shlex.quote(part) for part in argv),
            'exit_code': -1,
            'duration_seconds': round(ended - started, 3),
            'error': str(exc),
            'stdout': '',
            'stderr': str(exc),
        }


def _parse_pytest_count(text: str) -> Optional[int]:
    """Parse collected test count from pytest --collect-only output."""
    for line in reversed(text.splitlines()):
        line = line.strip()
        if ' tests collected' in line or line.endswith('tests collected'):
            parts = line.split()
            for i, part in enumerate(parts):
                if (
                    part == 'tests'
                    and i > 0
                    and i + 1 < len(parts)
                    and parts[i + 1] == 'collected'
                ):
                    try:
                        return int(parts[i - 1])
                    except ValueError:
                        return None
            if parts and parts[0].isdigit():
                return int(parts[0])
    return None


def _collect_pytest_counts(*, python: str, cwd: Path) -> dict[str, Any]:
    """Collect pytest test counts via --collect-only."""
    acceptance = _run(
        [python, '-m', 'pytest', 'tests/acceptance', '--collect-only', '-q'],
        cwd=cwd,
        timeout_seconds=300,
    )
    suite = _run(
        [python, '-m', 'pytest', '--collect-only', '-q'],
        cwd=cwd,
        timeout_seconds=300,
    )

    acceptance_count = None
    suite_collected = None
    suite_passed = None
    suite_failed = None
    suite_skipped = None

    # Parse collected counts from --collect-only output
    if acceptance.get('exit_code') is not None:
        acceptance_count = _parse_pytest_count(
            acceptance.get('stdout', '') + '\n' + acceptance.get('stderr', '')
        )
    if suite.get('exit_code') is not None:
        suite_collected = _parse_pytest_count(
            suite.get('stdout', '') + '\n' + suite.get('stderr', '')
        )

    return {
        'acceptance_collected': acceptance_count,
        'suite_collected': suite_collected,
        'suite_passed': suite_passed,
        'suite_failed': suite_failed,
        'suite_skipped': suite_skipped,
        'collect_commands': [acceptance, suite],
    }


def _collect_git_info(repo_root: Path) -> dict[str, Any]:
    """Collect git branch, commit, dirty flag, and tags."""
    branch_result = _run(
        ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
        cwd=repo_root,
        timeout_seconds=30,
    )
    commit_result = _run(
        ['git', 'rev-parse', 'HEAD'],
        cwd=repo_root,
        timeout_seconds=30,
    )
    status_result = _run(
        ['git', 'status', '--porcelain'],
        cwd=repo_root,
        timeout_seconds=30,
    )
    tags_result = _run(
        ['git', 'tag', '--points-at', 'HEAD'],
        cwd=repo_root,
        timeout_seconds=30,
    )

    return {
        'branch': branch_result.get('stdout', '').strip(),
        'commit': commit_result.get('stdout', '').strip(),
        'dirty': bool((status_result.get('stdout', '')).strip()),
        'tags': [
            t.strip() for t in (tags_result.get('stdout', '')).splitlines() if t.strip()
        ],
    }


def _collect_artifacts(repo_root: Path) -> list[dict]:
    """Collect artifact hashes for key release artifacts."""
    artifacts = []
    for rel in (
        'docs/acceptance.md',
        'docs/use-case-matrix.md',
        'docs/use-case-matrix.html',
        'docs/ergonomics-kpi.json',
        'docs/governance/release-process.md',
        'docs/release-checklist.md',
    ):
        path = repo_root / rel
        if path.is_file():
            artifacts.append(
                {
                    'path': rel,
                    'sha256': _sha256(path),
                    'bytes': path.stat().st_size,
                }
            )
    return artifacts


# ────────────────────────────────────────────────────────────────────────────
# Seven-loop evidence collection
# ────────────────────────────────────────────────────────────────────────────


def _check_spec_first(
    root: Path,
    evidence_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check Spec-first loop evidence (SCL-P0-001/002, CPP-P0-008)."""
    receipts: list[str] = []
    status = 'not_tested'
    trace_id: str = ''

    plan_gate_paths = list((root / 'docs' / 'governance').glob('*plan*gate*'))
    spec_plan_paths = list((root / 'docs' / 'governance').glob('*spec*plan*'))

    if plan_gate_paths or spec_plan_paths:
        newest = max(plan_gate_paths + spec_plan_paths, key=lambda p: p.stat().st_mtime)
        trace_id = f'file:{newest}:{newest.stat().st_mtime:.0f}'
        receipts.append(
            f'governance artifacts found: {len(plan_gate_paths) + len(spec_plan_paths)} file(s)'
        )

    plan_gate_mod = root / 'teaagent' / 'governance' / 'plan_gate.py'
    if plan_gate_mod.is_file():
        receipts.append('plan_gate.py module present')

    audit_log = root / '.teaagent' / 'audit.jsonl'
    if audit_log.is_file():
        try:
            spec_id_found = False
            spec_line_num = 0
            with audit_log.open('r', encoding='utf-8') as fh:
                for line_num, line in enumerate(fh):
                    if line_num > 5000:
                        break
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    payload = event.get('payload') or {}
                    if isinstance(payload, dict) and (
                        'spec_id' in payload or 'spec_hash' in payload
                    ):
                        spec_id_found = True
                        spec_line_num = line_num
                        break
            if spec_id_found:
                trace_id = f'audit:{spec_line_num}:spec_id'
                receipts.append('audit events contain spec_id/spec_hash references')
                status = 'verified'
            else:
                receipts.append(
                    'audit log found but no spec_id/spec_hash references detected'
                )
                status = 'partial'
        except OSError:
            receipts.append('unable to read audit log')
            status = 'partial'
    else:
        receipts.append('no audit log found (.teaagent/audit.jsonl)')
        if plan_gate_paths or spec_plan_paths:
            status = 'partial'

    if status == 'not_tested':
        status = 'partial' if receipts else 'not_tested'

    return {
        'name': 'spec_first',
        'status': status,
        'receipts': receipts,
        'trace_id': trace_id,
    }


def _check_dynamic_skill(
    root: Path,
    evidence_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check Dynamic workflow / skill lifecycle evidence (SCL-P0-003)."""
    receipts: list[str] = []
    status = 'not_tested'
    trace_id: str = ''

    lifecycle_mod = root / 'teaagent' / 'skill_lifecycle.py'
    if lifecycle_mod.is_file():
        trace_id = f'file:{lifecycle_mod}:{lifecycle_mod.stat().st_mtime:.0f}'
        receipts.append('skill_lifecycle.py module present')
        status = 'partial'

    provenance_mod = root / 'teaagent' / 'asset_provenance.py'
    if provenance_mod.is_file():
        receipts.append('asset_provenance.py module present')

    skill_dirs = [
        root / '.opencode' / 'skill',
        root / '.claude' / 'skills',
        root / '.config' / 'agent' / 'skills',
    ]
    builtin_skills_found = 0
    for skill_dir in skill_dirs:
        if skill_dir.is_dir():
            skill_files = list(skill_dir.rglob('SKILL.md'))
            builtin_skills_found += len(skill_files)
            if skill_files:
                receipts.append(f'skills discovered in {skill_dir}: {len(skill_files)}')

    if builtin_skills_found > 0:
        receipts.append(f'total built-in skills discovered: {builtin_skills_found}')
        status = 'verified'

    skill_loader = root / 'teaagent' / 'skill_loader.py'
    if skill_loader.is_file():
        receipts.append('skill_loader.py module present')

    return {
        'name': 'dynamic_skill',
        'status': status,
        'receipts': receipts,
        'trace_id': trace_id,
    }


def _check_loop_goal(
    root: Path,
    evidence_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check Loop/goal evidence (SCL-P0-004, SCL-P1-003)."""
    receipts: list[str] = []
    status = 'not_tested'
    trace_id: str = ''

    goal_mod = root / 'teaagent' / 'goal_record.py'
    if goal_mod.is_file():
        trace_id = f'file:{goal_mod}:{goal_mod.stat().st_mtime:.0f}'
        receipts.append('goal_record.py module present')

    try:
        sys.path.insert(0, str(root))
        from teaagent.goal_record import GoalStore

        store = GoalStore(root)
        goals = store.list()
        if goals:
            newest_goal = max(goals, key=lambda g: getattr(g, 'updated_at', '') or '')
            ts = getattr(newest_goal, 'updated_at', '')
            trace_id = f'goal:{ts}' if ts else trace_id
            receipts.append(f'GoalStore has {len(goals)} goal record(s)')
            status = 'verified'
        else:
            receipts.append('GoalStore is active but has no goal records')
            status = 'partial'
    except Exception:
        receipts.append('GoalStore import or access failed')

    return {
        'name': 'loop_goal',
        'status': status,
        'receipts': receipts,
        'trace_id': trace_id,
    }


def _check_model_routing(
    root: Path,
    evidence_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check Model routing evidence (SCL-P0-005, CPP-P0-001)."""
    receipts: list[str] = []
    status = 'not_tested'
    trace_id: str = ''

    routing_mod = root / 'teaagent' / 'model_routing.py'
    if routing_mod.is_file():
        trace_id = f'file:{routing_mod}:{routing_mod.stat().st_mtime:.0f}'
        receipts.append('model_routing.py module present')
        status = 'partial'

    audit_log = root / '.teaagent' / 'audit.jsonl'
    if audit_log.is_file():
        try:
            route_found = False
            route_line_num = 0
            with audit_log.open('r', encoding='utf-8') as fh:
                for line_num, line in enumerate(fh):
                    if line_num > 5000:
                        break
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if event.get('event_type') == 'model_route':
                        route_found = True
                        route_line_num = line_num
                        break
            if route_found:
                trace_id = f'audit:{route_line_num}:model_route'
                receipts.append('audit log contains model_route events')
                status = 'verified'
            else:
                receipts.append('no model_route events found in audit log')
                if status == 'not_tested':
                    status = 'partial'
        except OSError:
            receipts.append('unable to read audit log')
    else:
        receipts.append('no audit log found (.teaagent/audit.jsonl)')

    return {
        'name': 'model_routing',
        'status': status,
        'receipts': receipts,
        'trace_id': trace_id,
    }


def _check_synthesis_review(
    root: Path,
    evidence_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check Synthesis/review evidence (SCL-P0-006, SCL-P1-005)."""
    receipts: list[str] = []
    status = 'not_tested'
    trace_id: str = ''

    review_mod = root / 'teaagent' / 'governance' / 'review_gate.py'
    if review_mod.is_file():
        trace_id = f'file:{review_mod}:{review_mod.stat().st_mtime:.0f}'
        receipts.append('review_gate.py module present')
        status = 'partial'

    governance_dir = root / 'docs' / 'governance'
    review_files: list[Path] = []
    if governance_dir.is_dir():
        review_files.extend(governance_dir.glob('*review*'))
        review_files.extend(governance_dir.glob('*review*gate*'))

        if review_files:
            newest_review = max(review_files, key=lambda p: p.stat().st_mtime)
            trace_id = f'file:{newest_review}:{newest_review.stat().st_mtime:.0f}'
            receipts.append(
                f'{len(review_files)} review artifact(s) in docs/governance/'
            )
            status = 'verified'

    code_review_skill = root / '.opencode' / 'skill' / 'code-review' / 'SKILL.md'
    if code_review_skill.is_file():
        receipts.append('code-review skill installed')

    return {
        'name': 'synthesis_review',
        'status': status,
        'receipts': receipts,
        'trace_id': trace_id,
    }


def _check_precise_memory(
    root: Path,
    evidence_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check Precise memory evidence (SCL-P1-001/002)."""
    receipts: list[str] = []
    status = 'not_tested'
    trace_id: str = ''

    memory_mod = root / 'teaagent' / 'memory_store.py'
    if memory_mod.is_file():
        trace_id = f'file:{memory_mod}:{memory_mod.stat().st_mtime:.0f}'
        receipts.append('memory_store.py module present')
        status = 'partial'

    quarantine_mod = root / 'teaagent' / 'memory_quarantine.py'
    if quarantine_mod.is_file():
        receipts.append('memory_quarantine.py module present')

    workspace_mem = root / 'teaagent' / 'workspace_memory_catalog.py'
    if workspace_mem.is_file():
        receipts.append('workspace_memory_catalog.py module present')

    memory_dir = root / '.teaagent' / 'workspace_memory'
    if memory_dir.is_dir():
        mem_files = list(memory_dir.rglob('*.toml')) + list(memory_dir.rglob('*.json'))
        if mem_files:
            newest_mem = max(mem_files, key=lambda p: p.stat().st_mtime)
            trace_id = f'file:{newest_mem}:{newest_mem.stat().st_mtime:.0f}'
            receipts.append(f'{len(mem_files)} memory entries found in workspace')
            status = 'verified'
        else:
            receipts.append('memory directory exists but no entries found')

    quarantine_dir = root / '.teaagent' / 'memory_quarantine'
    if quarantine_dir.is_dir():
        quar_files = list(quarantine_dir.rglob('*.toml')) + list(
            quarantine_dir.rglob('*.json')
        )
        if quar_files:
            receipts.append(f'quarantine flow active: {len(quar_files)} entries')
        else:
            receipts.append('quarantine directory exists but is empty')

    return {
        'name': 'precise_memory',
        'status': status,
        'receipts': receipts,
        'trace_id': trace_id,
    }


def _check_human_review(
    root: Path,
    evidence_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check Human review evidence (SCL-P0-007, SCL-P1-006)."""
    receipts: list[str] = []
    status = 'not_tested'
    trace_id: str = ''

    approval_mod = root / 'teaagent' / 'approval_manager.py'
    if approval_mod.is_file():
        trace_id = f'file:{approval_mod}:{approval_mod.stat().st_mtime:.0f}'
        receipts.append('approval_manager.py module present')
        status = 'partial'

    audit_log = root / '.teaagent' / 'audit.jsonl'
    if audit_log.is_file():
        try:
            approval_count = 0
            with audit_log.open('r', encoding='utf-8') as fh:
                for line_num, line in enumerate(fh):
                    if line_num > 5000:
                        break
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    event_type = event.get('event_type', '')
                    if event_type in (
                        'approval_requested',
                        'approval_granted',
                        'approval_denied',
                        'tool_call_pending_approval',
                    ):
                        approval_count += 1
                        if not trace_id:
                            trace_id = f'audit:{line_num}:{event_type}'
            if approval_count > 0:
                receipts.append(f'{approval_count} approval gate event(s) in audit log')
                status = 'verified'
            else:
                receipts.append('no approval gate events found in audit log')
        except OSError:
            receipts.append('unable to read audit log')
    else:
        receipts.append('no audit log found (.teaagent/audit.jsonl)')

    governance_dir = root / 'docs' / 'governance'
    if governance_dir.is_dir():
        gate_files = list(governance_dir.glob('*gate*'))
        if gate_files:
            newest_gate = max(gate_files, key=lambda p: p.stat().st_mtime)
            if not trace_id:
                trace_id = f'file:{newest_gate}:{newest_gate.stat().st_mtime:.0f}'
            receipts.append(f'{len(gate_files)} gate artifact(s) in docs/governance/')
            if status != 'verified':
                status = 'verified' if receipts else 'partial'

    return {
        'name': 'human_review',
        'status': status,
        'receipts': receipts,
        'trace_id': trace_id,
    }


def _collect_seven_loop_evidence(
    root: Path,
    evidence_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Collect seven-loop evidence status from the workspace."""
    return {
        'spec_first': _check_spec_first(root, evidence_context=evidence_context),
        'dynamic_skill': _check_dynamic_skill(root, evidence_context=evidence_context),
        'loop_goal': _check_loop_goal(root, evidence_context=evidence_context),
        'model_routing': _check_model_routing(root, evidence_context=evidence_context),
        'synthesis_review': _check_synthesis_review(
            root, evidence_context=evidence_context
        ),
        'precise_memory': _check_precise_memory(
            root, evidence_context=evidence_context
        ),
        'human_review': _check_human_review(root, evidence_context=evidence_context),
    }


# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────


def build_release_evidence_bundle(
    profile: str = 'release',
    root: Optional[str | Path] = None,
) -> ReleaseEvidenceBundle:
    """Build a release evidence bundle with seven-loop status.

    Args:
        profile: One of 'release', 'full', or 'counts-only'.
        root: Workspace root directory. Defaults to current directory.

    Returns:
        A ``ReleaseEvidenceBundle`` with all collected evidence.
    """
    repo_root = Path(root).resolve() if root else Path.cwd().resolve()
    created_at = datetime.now(timezone.utc).isoformat()
    python = sys.executable

    # Platform info
    platform_info = {
        'python_version': sys.version.split()[0],
        'os': platform.system(),
        'platform': platform.platform(),
    }

    # Git info
    git_info = _collect_git_info(repo_root)

    # Pytest counts
    pytest_counts = _collect_pytest_counts(python=python, cwd=repo_root)

    # Run gate commands (when profile is release or full)
    commands: list[dict] = []
    if profile in ('release', 'full'):
        # Pre-commit checks
        commands.append(
            _run(
                ['pre-commit', 'run', '-a'],
                cwd=repo_root,
                timeout_seconds=900,
            )
        )
        # Acceptance tests
        commands.append(
            _run(
                [python, 'scripts/run_acceptance_tier.py', '--tier', 'all'],
                cwd=repo_root,
                timeout_seconds=900,
            )
        )

    # Seven-loop evidence
    evidence_context = {
        'created_at': created_at,
        'git_commit': git_info.get('commit', ''),
        'run_profile': profile,
    }
    seven_loop = _collect_seven_loop_evidence(
        repo_root, evidence_context=evidence_context
    )

    # Artifact hashes
    artifacts = _collect_artifacts(repo_root)

    # Compute evidence status fields
    commands_ok = (
        all(c.get('exit_code', -1) == 0 for c in commands) if commands else True
    )
    collection_ok = bool(git_info.get('commit')) and bool(
        pytest_counts.get('suite_collected') is not None
    )
    evidence_complete = all(
        loop.get('status') == 'verified' for loop in seven_loop.values()
    )

    return ReleaseEvidenceBundle(
        commands_ok=commands_ok,
        collection_ok=collection_ok,
        evidence_complete=evidence_complete,
        created_at=created_at,
        repo_root=str(repo_root),
        run_profile=profile,
        platform=platform_info,
        git=git_info,
        pytest_counts=pytest_counts,
        seven_loop_evidence=seven_loop,
        commands=commands,
        artifacts=artifacts,
    )


def write_release_evidence_bundle(
    bundle: ReleaseEvidenceBundle,
    output_path: str | Path,
) -> Path:
    """Write a release evidence bundle to a JSON file.

    Args:
        bundle: The ``ReleaseEvidenceBundle`` to write.
        output_path: Output path for the JSON file.

    Returns:
        The resolved output path that was written to.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        'ok': bundle.ok,
        'commands_ok': bundle.commands_ok,
        'collection_ok': bundle.collection_ok,
        'evidence_complete': bundle.evidence_complete,
        'created_at': bundle.created_at,
        'repo_root': bundle.repo_root,
        'run_profile': bundle.run_profile,
        'platform': bundle.platform,
        'git': bundle.git,
        'pytest_counts': bundle.pytest_counts,
        'seven_loop_evidence': bundle.seven_loop_evidence,
        'commands': bundle.commands,
        'artifacts': bundle.artifacts,
    }

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    return output_path
