"""Parallel executor for tournament subagents.

Supports in-process ``SubagentManager`` runs (centralized approval queue) or a
subprocess ``teaagent run`` fallback when no manager is configured.
"""

from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from teaagent.subagent_run_context import (
    bind_parallel_approval_mode,
    bind_parent_run_id,
    reset_parallel_approval_mode,
    reset_parent_run_id,
)
from teaagent.subagents._approval_queue import get_approval_queue


@dataclass
class AgentResult:
    """Result from a tournament subagent."""

    approach_id: str
    branch_name: str
    success: bool
    output: str
    error: Optional[str]
    execution_time: float
    metadata: Dict[str, Any]


class ParallelExecutor:
    """Executor for parallel tournament subagents."""

    def __init__(
        self,
        root: Path,
        timeout: int = 300,
        *,
        parent_run_id: Optional[str] = None,
        subagent_manager: Any = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.timeout = timeout
        self._parent_run_id = parent_run_id
        self._subagent_manager = subagent_manager
        self.results: List[AgentResult] = []

    def execute_parallel(
        self,
        task: str,
        branches: List[str],
        approach_hints: List[str],
        *,
        parent_run_id: Optional[str] = None,
    ) -> List[AgentResult]:
        """Execute subagents in parallel on different branches."""
        if len(branches) != len(approach_hints):
            raise ValueError('Branches and approach hints must have same length')

        parent_id = parent_run_id or self._parent_run_id or uuid4().hex
        self._parent_run_id = parent_id
        get_approval_queue(parent_id)

        self.results = []
        threads: list[threading.Thread] = []
        results_lock = threading.Lock()

        for index, (branch, hint) in enumerate(
            zip(branches, approach_hints, strict=True)
        ):
            thread = threading.Thread(
                target=self._execute_agent,
                args=(task, branch, hint, index, parent_id, results_lock),
            )
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join(timeout=self.timeout + 10)

        return self.results

    def _execute_agent(
        self,
        task: str,
        branch: str,
        hint: str,
        index: int,
        parent_run_id: str,
        results_lock: threading.Lock,
    ) -> None:
        if self._subagent_manager is not None:
            self._execute_agent_via_subagent_manager(
                task,
                branch,
                hint,
                index,
                parent_run_id,
                results_lock,
            )
        else:
            self._execute_agent_subprocess(
                task, branch, hint, index, parent_run_id, results_lock
            )

    def _execute_agent_via_subagent_manager(
        self,
        task: str,
        branch: str,
        hint: str,
        index: int,
        parent_run_id: str,
        results_lock: threading.Lock,
    ) -> None:
        start_time = time.time()
        parallel_token = bind_parallel_approval_mode(True)
        parent_token = bind_parent_run_id(parent_run_id)
        task_spec = f'{task}\n\nTournament approach ({branch}): {hint}'
        try:
            payload = self._subagent_manager.run_subagent(
                task=task_spec,
                parent_run_id=parent_run_id,
                depth=0,
                batch_index=index,
                isolation='worktree',
            )
            status = str(payload.get('status', 'error'))
            success = status == 'completed'
            output = str(payload.get('final_answer') or payload.get('run_id', ''))
            error = None if success else str(payload.get('message', status))
        except Exception as exc:
            success = False
            output = ''
            error = str(exc)
        finally:
            reset_parent_run_id(parent_token)
            reset_parallel_approval_mode(parallel_token)

        execution_time = time.time() - start_time
        queue = get_approval_queue(parent_run_id)
        agent_result = AgentResult(
            approach_id=f'opt{index + 1}',
            branch_name=branch,
            success=success,
            output=output,
            error=error,
            execution_time=execution_time,
            metadata={
                'execution': 'subagent_manager',
                'parent_run_id': parent_run_id,
                'pending_approvals': len(queue.get_pending_requests()),
                'branch': branch,
            },
        )
        with results_lock:
            self.results.append(agent_result)

    def _execute_agent_subprocess(
        self,
        task: str,
        branch: str,
        hint: str,
        index: int,
        parent_run_id: str,
        results_lock: threading.Lock,
    ) -> None:
        start_time = time.time()
        execution_root = self.root

        try:
            execution_root = self._resolve_execution_root(branch, execution_root)
            subprocess.run(
                ['git', 'checkout', branch],
                cwd=execution_root,
                capture_output=True,
                text=True,
                check=True,
            )
            command = [
                'teaagent',
                'run',
                f'{task} (approach: {hint})',
                '--root',
                str(execution_root),
            ]
            result = subprocess.run(
                command,
                cwd=execution_root,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            success = result.returncode == 0
            output = result.stdout
            error = result.stderr if result.stderr else None
        except subprocess.TimeoutExpired:
            success = False
            output = ''
            error = f'Agent execution timed out after {self.timeout}s'
        except subprocess.CalledProcessError as exc:
            success = False
            output = exc.stdout or ''
            error = exc.stderr or str(exc)
        except Exception as exc:
            success = False
            output = ''
            error = str(exc)

        execution_time = time.time() - start_time
        agent_result = AgentResult(
            approach_id=f'opt{index + 1}',
            branch_name=branch,
            success=success,
            output=output,
            error=error,
            execution_time=execution_time,
            metadata={
                'execution': 'subprocess',
                'parent_run_id': parent_run_id,
                'sandbox_enforced': True,
            },
        )
        with results_lock:
            self.results.append(agent_result)

    def _resolve_execution_root(self, branch: str, execution_root: Path) -> Path:
        try:
            branch_check = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=execution_root,
                capture_output=True,
                text=True,
                check=True,
            )
            current_branch = branch_check.stdout.strip()
            if current_branch in {'main', 'master'}:
                worktree_path = execution_root / '.teaagent' / 'worktrees' / branch
                subprocess.run(
                    ['git', 'worktree', 'add', str(worktree_path), branch],
                    cwd=execution_root,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return worktree_path
        except subprocess.CalledProcessError:
            pass
        return execution_root


def parallel_executor_with_manager(
    root: Path,
    *,
    config: Any,
    adapter: Any,
    registry: Any,
    timeout: int = 300,
    parent_run_id: Optional[str] = None,
) -> ParallelExecutor:
    """Build an executor that runs tournament branches via ``SubagentManager``."""
    from teaagent.subagents._manager import SubagentManager

    manager = SubagentManager(
        root=Path(root).resolve(),
        parent_config=config,
        parent_adapter=adapter,
    )
    manager.bind_registry(registry)
    return ParallelExecutor(
        root,
        timeout,
        parent_run_id=parent_run_id,
        subagent_manager=manager,
    )
