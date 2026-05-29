"""Execute skill tool modules inside routed sandboxes."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from teaagent.consensus import RiskLevel
from teaagent.docker_sandbox import DockerSandbox
from teaagent.skill_router import (
    SandboxType,
    SkillIsolationPlan,
    SkillRouter,
    plan_skill_isolation,
)
from teaagent.wasm_runtime import WASMRuntime, is_wasm_available

logger = logging.getLogger(__name__)

_MEMORY_PATTERN = re.compile(r'^(\d+(?:\.\d+)?)\s*([kmg]?)b?$', re.IGNORECASE)


@dataclass(frozen=True)
class SkillExecutionResult:
    """Outcome of executing a skill tool module."""

    success: bool
    sandbox_type: SandboxType
    output: Any = None
    error: str = ''
    execution_backend: str = ''
    reason: str = ''


def _find_tool_file(skill_path: Path) -> Path:
    tool_py = skill_path / 'tool.py'
    if tool_py.is_file():
        return tool_py
    py_files = sorted(skill_path.glob('*.py'))
    if py_files:
        return py_files[0]
    raise FileNotFoundError(f'No Python tool module found under {skill_path}')


def _find_wasm_file(skill_path: Path) -> Optional[Path]:
    for name in ('tool.wasm', 'skill.wasm'):
        candidate = skill_path / name
        if candidate.is_file():
            return candidate
    wasm_files = sorted(skill_path.glob('*.wasm'))
    return wasm_files[0] if wasm_files else None


def _parse_memory_mb(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    match = _MEMORY_PATTERN.match(value.strip())
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2).lower()
    if unit == 'g':
        return amount * 1024
    if unit == 'k':
        return amount / 1024
    return amount


def _build_docker_runner_code(tool_code: str, payload: dict[str, Any]) -> str:
    payload_json = json.dumps(payload)
    runner_tail = (
        f'__teaagent_payload__ = {payload_json}\n'
        f'__teaagent_result__ = run(__teaagent_payload__)\n'
        "print(json.dumps({'ok': True, 'result': __teaagent_result__}))\n"
    )
    lines = tool_code.splitlines()
    insert_at = 0
    while insert_at < len(lines) and (
        not lines[insert_at].strip()
        or lines[insert_at].startswith('#')
        or lines[insert_at].startswith('from __future__')
    ):
        insert_at += 1
    header = '\n'.join(lines[:insert_at])
    body = '\n'.join(lines[insert_at:])
    parts: list[str] = []
    if header:
        parts.append(header)
    parts.append('import json')
    if body:
        parts.append(body)
    parts.append(runner_tail)
    return '\n'.join(parts) + '\n'


def _execute_python_subprocess(
    skill_path: Path,
    tool_code: str,
    payload: dict[str, Any],
    *,
    sandbox_type: SandboxType,
    backend: str,
) -> SkillExecutionResult:
    script = _build_docker_runner_code(tool_code, payload)
    try:
        completed = subprocess.run(
            [sys.executable, '-c', script],
            cwd=skill_path,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return SkillExecutionResult(
            success=False,
            sandbox_type=sandbox_type,
            error='skill execution timed out',
            execution_backend=backend,
        )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or 'skill execution failed').strip()
        return SkillExecutionResult(
            success=False,
            sandbox_type=sandbox_type,
            error=detail,
            execution_backend=backend,
        )
    try:
        parsed = json.loads(completed.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        return SkillExecutionResult(
            success=False,
            sandbox_type=sandbox_type,
            error=f'Invalid skill output: {exc}',
            execution_backend=backend,
        )
    if not parsed.get('ok'):
        return SkillExecutionResult(
            success=False,
            sandbox_type=sandbox_type,
            error='Skill reported failure',
            execution_backend=backend,
        )
    return SkillExecutionResult(
        success=True,
        sandbox_type=sandbox_type,
        output=parsed.get('result'),
        execution_backend=backend,
    )


def _execute_wasm_module(
    skill_path: Path,
    wasm_path: Path,
    payload: dict[str, Any],
    *,
    memory_limit_mb: int,
) -> SkillExecutionResult:
    if not is_wasm_available():
        return SkillExecutionResult(
            success=False,
            sandbox_type=SandboxType.WASM,
            error='WASM runtime not available',
            execution_backend='wasm',
        )
    runtime = WASMRuntime(memory_limit_mb=memory_limit_mb)
    if not runtime.load_module(wasm_path):
        return SkillExecutionResult(
            success=False,
            sandbox_type=SandboxType.WASM,
            error=f'Failed to load WASM module: {wasm_path}',
            execution_backend='wasm',
        )
    try:
        for function_name in ('run', 'main', 'execute'):
            exec_result = runtime.execute(function_name, json.dumps(payload))
            if exec_result.success:
                try:
                    output: Any = json.loads(exec_result.output)
                except json.JSONDecodeError:
                    output = exec_result.output
                return SkillExecutionResult(
                    success=True,
                    sandbox_type=SandboxType.WASM,
                    output=output,
                    execution_backend='wasm',
                )
            if exec_result.error and 'not found' not in exec_result.error.lower():
                return SkillExecutionResult(
                    success=False,
                    sandbox_type=SandboxType.WASM,
                    error=exec_result.error or 'WASM execution failed',
                    execution_backend='wasm',
                )
        return SkillExecutionResult(
            success=False,
            sandbox_type=SandboxType.WASM,
            error='No callable WASM export found (run/main/execute)',
            execution_backend='wasm',
        )
    finally:
        runtime.cleanup()


def _execute_docker(
    skill_path: Path,
    tool_code: str,
    payload: dict[str, Any],
    plan: SkillIsolationPlan,
) -> SkillExecutionResult:
    sandbox = DockerSandbox(
        cpu_cores=plan.cpu_quota or 1.0,
        memory_limit_mb=_parse_memory_mb(plan.memory_limit) or 512.0,
        workspace_mount_path=skill_path.parent,
        run_id='skill-execute',
    )
    started = sandbox.start()
    if started.status != 'started':
        logger.info('Docker unavailable for skill execution; falling back to code mode')
        return _execute_python_subprocess(
            skill_path,
            tool_code,
            payload,
            sandbox_type=SandboxType.DOCKER,
            backend='docker_fallback_subprocess',
        )
    try:
        result = sandbox.execute_code(_build_docker_runner_code(tool_code, payload))
        if result.status == 'aborted':
            return SkillExecutionResult(
                success=False,
                sandbox_type=SandboxType.DOCKER,
                error=result.message or 'docker sandbox aborted',
                execution_backend='docker',
            )
        if result.exit_code != 0:
            detail = (result.stderr or result.stdout or 'docker execution failed').strip()
            return SkillExecutionResult(
                success=False,
                sandbox_type=SandboxType.DOCKER,
                error=detail,
                execution_backend='docker',
            )
        try:
            parsed = json.loads(result.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError) as exc:
            return SkillExecutionResult(
                success=False,
                sandbox_type=SandboxType.DOCKER,
                error=f'Invalid docker skill output: {exc}',
                execution_backend='docker',
            )
        if not parsed.get('ok'):
            return SkillExecutionResult(
                success=False,
                sandbox_type=SandboxType.DOCKER,
                error='Skill reported failure in docker sandbox',
                execution_backend='docker',
            )
        return SkillExecutionResult(
            success=True,
            sandbox_type=SandboxType.DOCKER,
            output=parsed.get('result'),
            execution_backend='docker',
        )
    finally:
        sandbox.cleanup()


def execute_skill(
    skill_path: str | Path,
    payload: dict[str, Any] | None = None,
    *,
    risk_level: RiskLevel = RiskLevel.MEDIUM,
    router: Optional[SkillRouter] = None,
    preferred_sandbox: Optional[SandboxType] = None,
) -> SkillExecutionResult:
    """Route and execute a skill's ``run(payload)`` entrypoint."""
    path = Path(skill_path).resolve()
    if not path.is_dir():
        return SkillExecutionResult(
            success=False,
            sandbox_type=SandboxType.DIRECTORY_SNAPSHOT,
            error=f'Skill path does not exist: {path}',
        )

    skill_router = router or SkillRouter()
    plan = plan_skill_isolation(path, risk_level, router=skill_router)
    decision = skill_router.route_skill(path, risk_level, preferred_sandbox)
    safe_payload = dict(payload or {})

    try:
        tool_code = _find_tool_file(path).read_text(encoding='utf-8')
    except FileNotFoundError as exc:
        return SkillExecutionResult(
            success=False,
            sandbox_type=decision.sandbox_type,
            error=str(exc),
            reason=decision.reason,
        )

    if decision.sandbox_type == SandboxType.WASM:
        wasm_path = _find_wasm_file(path)
        if wasm_path is not None:
            return _execute_wasm_module(
                path,
                wasm_path,
                safe_payload,
                memory_limit_mb=skill_router.wasm_memory_limit_mb,
            )
        return _execute_python_subprocess(
            path,
            tool_code,
            safe_payload,
            sandbox_type=SandboxType.WASM,
            backend='wasm_compat_python',
        )

    if decision.sandbox_type == SandboxType.DOCKER:
        return _execute_docker(path, tool_code, safe_payload, plan)

    return _execute_python_subprocess(
        path,
        tool_code,
        safe_payload,
        sandbox_type=decision.sandbox_type,
        backend='subprocess',
    )
