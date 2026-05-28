"""Multi-agent swarm orchestration for parallel task execution.

This module provides SwarmManager for coordinating multiple subagents
with OSSandbox isolation, enabling parallel experiment branches and
automated code review between subagents.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from teaagent.consensus import (
    ConsensusConfig,
    ConsensusEngine,
    ConsensusStatus,
    PeerRegistry,
    RiskLevel,
)
from teaagent.git_sandbox import GitBranchSandbox
from teaagent.resource_monitor import is_process_alive

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SubagentTask:
    """Task definition for a subagent."""

    task_id: str
    description: str
    context: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    risk_level: RiskLevel = RiskLevel.MEDIUM
    require_consensus: bool = False


@dataclass(frozen=True)
class SubagentResult:
    """Result from a subagent execution."""

    task_id: str
    success: bool
    branch_name: Optional[str] = None
    output: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    test_results: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CodeReview:
    """Code review result between subagents."""

    reviewer_task_id: str
    target_task_id: str
    score: float  # 0.0 to 1.0
    findings: list[str] = field(default_factory=list)
    recommendation: str = ''  # "approve", "reject", "request_changes"


@dataclass(frozen=True)
class SwarmReport:
    """Final report from swarm execution."""

    total_subagents: int
    successful_subagents: int
    failed_subagents: int
    results: list[SubagentResult]
    code_reviews: list[CodeReview]
    best_result: Optional[SubagentResult] = None
    total_execution_time_ms: float = 0.0
    tournament_winner_id: Optional[str] = None
    tournament_winner_score: float = 0.0


@dataclass(frozen=True)
class PromptFitnessMetrics:
    """Normalized metrics used by prompt tournament scoring."""

    success: int
    tokens: float
    min_tokens: float
    time_seconds: float
    min_time_seconds: float
    errors: int


def compute_prompt_fitness_score(metrics: PromptFitnessMetrics) -> float:
    """Compute prompt fitness score with hard success gate.

    If success is 0, score is forced to 0.
    """
    if metrics.success <= 0:
        return 0.0
    if metrics.tokens <= 0 or metrics.min_tokens <= 0:
        raise ValueError('tokens and min_tokens must be positive')
    if metrics.time_seconds <= 0 or metrics.min_time_seconds <= 0:
        raise ValueError('time_seconds and min_time_seconds must be positive')
    if metrics.errors < 0:
        raise ValueError('errors must be non-negative')

    return (
        0.4 * float(metrics.success)
        + 0.3 * (metrics.min_tokens / metrics.tokens)
        + 0.2 * (metrics.min_time_seconds / metrics.time_seconds)
        + 0.1 * (1.0 / float(metrics.errors + 1))
    )


def fitness_metrics_from_result(
    result: SubagentResult,
    *,
    peer_results: list[SubagentResult],
) -> PromptFitnessMetrics:
    """Build tournament metrics from a subagent result and peer baselines."""
    token_values = [
        float(item.test_results.get('tokens', 1.0)) for item in peer_results
    ]
    time_values = [
        max(item.execution_time_ms / 1000.0, 0.001) for item in peer_results
    ]
    min_tokens = min(token_values) if token_values else 1.0
    min_time = min(time_values) if time_values else 1.0
    return PromptFitnessMetrics(
        success=1 if result.success else 0,
        tokens=float(result.test_results.get('tokens', min_tokens)),
        min_tokens=min_tokens,
        time_seconds=max(result.execution_time_ms / 1000.0, 0.001),
        min_time_seconds=min_time,
        errors=int(result.test_results.get('errors', 0)),
    )


def rank_prompt_tournament(
    candidates: list[tuple[str, str, PromptFitnessMetrics]],
) -> list[tuple[str, float, str]]:
    """Rank prompt variants by fitness score (highest first)."""
    ranked: list[tuple[str, float, str]] = []
    for task_id, prompt, metrics in candidates:
        ranked.append((task_id, compute_prompt_fitness_score(metrics), prompt))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked


def save_prompt_to_gene_pool(
    root: str | Path,
    *,
    prompt: str,
    score: float,
    task_id: str = '',
) -> Path:
    """Append a high-scoring prompt variant to the local gene pool store."""
    pool_dir = Path(root).resolve() / '.teaagent'
    pool_dir.mkdir(parents=True, exist_ok=True)
    path = pool_dir / 'prompt_gene_pool.jsonl'
    entry = {
        'prompt': prompt,
        'score': score,
        'task_id': task_id,
        'saved_at': time.time(),
    }
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(entry, separators=(',', ':')) + '\n')
    return path


class Subagent:
    """Individual subagent with isolated sandbox execution."""

    def __init__(self, task: SubagentTask, root: str | Path) -> None:
        self._task = task
        self._root = Path(root).resolve()
        self._sandbox = GitBranchSandbox(self._root, task.task_id)
        self._result: Optional[SubagentResult] = None

    def execute(self) -> SubagentResult:
        """Execute the subagent task in isolated sandbox."""
        import time

        start_time = time.perf_counter()

        if not self._sandbox.is_available():
            return SubagentResult(
                task_id=self._task.task_id,
                success=False,
                error='Git sandbox not available',
            )

        # Start sandbox branch
        sandbox_result = self._sandbox.start(auto_stash=True)
        if not sandbox_result.success:
            return SubagentResult(
                task_id=self._task.task_id,
                success=False,
                error=sandbox_result.error or 'Failed to start sandbox',
            )

        try:
            # Execute task (placeholder for actual agent execution)
            # In production, this would invoke the LLM agent with the task
            output = self._execute_task()

            execution_time = (time.perf_counter() - start_time) * 1000

            return SubagentResult(
                task_id=self._task.task_id,
                success=True,
                branch_name=sandbox_result.branch_name,
                output=output,
                execution_time_ms=execution_time,
            )
        except Exception as exc:
            execution_time = (time.perf_counter() - start_time) * 1000
            return SubagentResult(
                task_id=self._task.task_id,
                success=False,
                branch_name=sandbox_result.branch_name,
                error=str(exc),
                execution_time_ms=execution_time,
            )

    def _execute_task(self) -> dict[str, Any]:
        """Execute the actual task (placeholder for LLM agent call)."""
        # This is a placeholder - in production, this would:
        # 1. Invoke the LLM agent with the task description
        # 2. Allow the agent to use tools within the sandbox
        # 3. Capture the output and any code changes

        # For now, return a mock result
        return {
            'task': self._task.description,
            'status': 'completed',
            'files_modified': [],
            'changes_summary': 'Mock execution',
        }

    def cleanup(self) -> None:
        """Cleanup sandbox branch after execution."""
        if self._sandbox.is_available() and self._sandbox._original_branch:
            # Switch back to original branch
            with suppress(subprocess.CalledProcessError):
                subprocess.run(
                    ['git', 'checkout', self._sandbox._original_branch],
                    cwd=self._root,
                    capture_output=True,
                    check=True,
                )


class SwarmManager:
    """Orchestrates multiple subagents with parallel execution."""

    def __init__(
        self,
        root: str | Path,
        max_parallel: int = 3,
        enable_consensus: bool = False,
        peer_registry: Optional[PeerRegistry] = None,
        consensus_config: Optional[ConsensusConfig] = None,
        lock_timeout_seconds: int = 60,
        prompt_by_task_id: dict[str, str] | None = None,
    ) -> None:
        self._root = Path(root).resolve()
        self._max_parallel = max_parallel
        self._prompt_by_task_id = dict(prompt_by_task_id or {})
        self._subagents: list[Subagent] = []
        self._results: list[SubagentResult] = []
        self._enable_consensus = enable_consensus
        self._peer_registry = peer_registry or PeerRegistry()
        self._consensus_config = consensus_config or ConsensusConfig()
        self._consensus_engine: Optional[ConsensusEngine] = None
        self._lock_timeout_seconds = lock_timeout_seconds
        self._subagent_pids: dict[str, int] = {}
        self._subagent_heartbeats: dict[str, float] = {}
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_stop_event = threading.Event()

        if self._enable_consensus:
            self._consensus_engine = ConsensusEngine(
                peer_registry=self._peer_registry,
                config=self._consensus_config,
            )

    def add_subagent(self, task: SubagentTask) -> None:
        """Add a subagent task to the swarm."""
        subagent = Subagent(task, self._root)
        self._subagents.append(subagent)

    def _start_heartbeat_monitor(self) -> None:
        """Start background heartbeat monitoring for subagent timeout detection."""
        if self._heartbeat_thread is not None:
            return

        self._heartbeat_stop_event.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_monitor_loop, daemon=True
        )
        self._heartbeat_thread.start()

    def _stop_heartbeat_monitor(self) -> None:
        """Stop heartbeat monitoring."""
        if self._heartbeat_thread is not None:
            self._heartbeat_stop_event.set()
            self._heartbeat_thread.join(timeout=5)
            self._heartbeat_thread = None

    def _heartbeat_monitor_loop(self) -> None:
        """Background loop to monitor subagent heartbeats and detect timeouts."""
        while not self._heartbeat_stop_event.wait(5):  # Check every 5 seconds
            current_time = time.time()
            for task_id, last_heartbeat in list(self._subagent_heartbeats.items()):
                if current_time - last_heartbeat > self._lock_timeout_seconds:
                    pid = self._subagent_pids.get(task_id)
                    if pid and not is_process_alive(pid):
                        logger.warning(
                            f'Subagent {task_id} (PID {pid}) appears dead, '
                            f'timeout after {self._lock_timeout_seconds}s'
                        )
                        # Mark as failed and remove from tracking
                        self._subagent_heartbeats.pop(task_id, None)
                        self._subagent_pids.pop(task_id, None)

    def _update_subagent_heartbeat(self, task_id: str, pid: int) -> None:
        """Update heartbeat timestamp for a subagent."""
        self._subagent_pids[task_id] = pid
        self._subagent_heartbeats[task_id] = time.time()

    def execute_swarm(self) -> SwarmReport:
        """Execute all subagents in parallel and collect results."""
        import time

        start_time = time.perf_counter()

        if not self._subagents:
            return SwarmReport(
                total_subagents=0,
                successful_subagents=0,
                failed_subagents=0,
                results=[],
                code_reviews=[],
            )

        # Start heartbeat monitoring
        self._start_heartbeat_monitor()

        try:
            # Check consensus for high-risk tasks if enabled
            if self._enable_consensus and self._consensus_engine:
                consensus_results = self._check_consensus_for_tasks()
                if not consensus_results.get('all_approved', True):
                    # Some tasks were not approved, filter them out
                    self._filter_subagents_by_consensus(consensus_results)

            # Execute subagents in parallel with thread pool
            results = []
            with ThreadPoolExecutor(max_workers=self._max_parallel) as executor:
                future_to_subagent = {
                    executor.submit(subagent.execute): subagent
                    for subagent in self._subagents
                }

                for future in as_completed(future_to_subagent):
                    subagent = future_to_subagent[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as exc:
                        results.append(
                            SubagentResult(
                                task_id=subagent._task.task_id,
                                success=False,
                                error=str(exc),
                            )
                        )

            # Cleanup all subagents
            for subagent in self._subagents:
                subagent.cleanup()

            self._results = results
            total_time = (time.perf_counter() - start_time) * 1000

            successful = sum(1 for r in results if r.success)
            failed = len(results) - successful

            winner_id, winner_score, best_result = self._select_tournament_winner(
                results
            )

            return SwarmReport(
                total_subagents=len(self._subagents),
                successful_subagents=successful,
                failed_subagents=failed,
                results=results,
                code_reviews=[],  # Will be populated by code review phase
                best_result=best_result,
                total_execution_time_ms=total_time,
                tournament_winner_id=winner_id,
                tournament_winner_score=winner_score,
            )
        finally:
            # Stop heartbeat monitoring
            self._stop_heartbeat_monitor()

    def _select_tournament_winner(
        self, results: list[SubagentResult]
    ) -> tuple[Optional[str], float, Optional[SubagentResult]]:
        """Select best branch via prompt fitness tournament when prompts are set."""
        if not self._prompt_by_task_id:
            best_result = next((r for r in results if r.success), None)
            return None, 0.0, best_result

        candidates: list[tuple[str, str, PromptFitnessMetrics]] = []
        for result in results:
            prompt = self._prompt_by_task_id.get(result.task_id)
            if prompt is None:
                continue
            metrics = fitness_metrics_from_result(result, peer_results=results)
            candidates.append((result.task_id, prompt, metrics))

        if not candidates:
            best_result = next((r for r in results if r.success), None)
            return None, 0.0, best_result

        ranked = rank_prompt_tournament(candidates)
        winner_id, winner_score, winner_prompt = ranked[0]
        save_prompt_to_gene_pool(
            self._root,
            prompt=winner_prompt,
            score=winner_score,
            task_id=winner_id,
        )
        best_result = next(
            (r for r in results if r.task_id == winner_id),
            next((r for r in results if r.success), None),
        )
        return winner_id, winner_score, best_result

    def _check_consensus_for_tasks(self) -> dict[str, Any]:
        """Check consensus for tasks that require it.

        Returns:
            Dictionary with 'all_approved' boolean and 'task_results' mapping
        """
        if not self._consensus_engine:
            return {'all_approved': True, 'task_results': {}}

        task_results: dict[str, dict[str, Any]] = {}
        all_approved = True

        for subagent in self._subagents:
            if subagent._task.require_consensus:
                # Request consensus for this task
                try:
                    state = self._consensus_engine.request_consensus(
                        task_description=subagent._task.description,
                        risk_level=subagent._task.risk_level,
                        proposed_by='swarm-orchestrator',
                    )

                    # Wait for consensus (simplified - in production, this would be async)
                    # For now, we'll check if it's already approved or fallback
                    status = self._consensus_engine.get_consensus_status(
                        state.proposal.id
                    )

                    if status and status.status == ConsensusStatus.APPROVED:
                        task_results[subagent._task.task_id] = {
                            'approved': True,
                            'attestation': self._consensus_engine.generate_attestation(
                                state.proposal.id
                            ),
                        }
                    else:
                        task_results[subagent._task.task_id] = {
                            'approved': False,
                            'reason': 'Consensus not reached',
                        }
                        all_approved = False
                except Exception as exc:
                    task_results[subagent._task.task_id] = {
                        'approved': False,
                        'reason': str(exc),
                    }
                    all_approved = False

        return {'all_approved': all_approved, 'task_results': task_results}

    def _filter_subagents_by_consensus(self, consensus_results: dict[str, Any]) -> None:
        """Filter out subagents whose tasks were not approved by consensus.

        Args:
            consensus_results: Results from consensus checking
        """
        task_results = consensus_results.get('task_results', {})
        self._subagents = [
            subagent
            for subagent in self._subagents
            if not subagent._task.require_consensus
            or task_results.get(subagent._task.task_id, {}).get('approved', False)
        ]

    def enable_consensus_mode(
        self,
        peer_registry: Optional[PeerRegistry] = None,
        consensus_config: Optional[ConsensusConfig] = None,
    ) -> None:
        """Enable consensus mode for the swarm.

        Args:
            peer_registry: Peer registry (uses existing if None)
            consensus_config: Consensus config (uses existing if None)
        """
        self._enable_consensus = True
        if peer_registry:
            self._peer_registry = peer_registry
        if consensus_config:
            self._consensus_config = consensus_config

        self._consensus_engine = ConsensusEngine(
            peer_registry=self._peer_registry,
            config=self._consensus_config,
        )

    def disable_consensus_mode(self) -> None:
        """Disable consensus mode for the swarm."""
        self._enable_consensus = False
        self._consensus_engine = None

    def run_code_reviews(self, report: SwarmReport) -> list[CodeReview]:
        """Run automated code reviews between subagent results."""
        reviews = []

        successful_results = [r for r in report.results if r.success]

        # Pairwise review between all successful subagents
        for i, reviewer in enumerate(successful_results):
            for j, target in enumerate(successful_results):
                if i == j:
                    continue

                review = self._review_subagent(reviewer, target)
                reviews.append(review)

        return reviews

    def _review_subagent(
        self, reviewer: SubagentResult, target: SubagentResult
    ) -> CodeReview:
        """Review target subagent result from reviewer's perspective."""
        # Placeholder for actual code review logic
        # In production, this would:
        # 1. Compare the code changes between branches
        # 2. Run tests on both branches
        # 3. Use LLM to generate review comments
        # 4. Score based on test results and code quality

        # For now, return a mock review
        return CodeReview(
            reviewer_task_id=reviewer.task_id,
            target_task_id=target.task_id,
            score=0.8,  # Mock score
            findings=['Mock code review finding'],
            recommendation='approve',
        )

    def select_best_result(
        self, report: SwarmReport, reviews: list[CodeReview]
    ) -> Optional[SubagentResult]:
        """Select the best result based on code reviews and execution metrics."""
        if not report.results:
            return None

        # Calculate aggregate scores for each result
        scores: dict[str, float] = {}

        for result in report.results:
            if not result.success:
                scores[result.task_id] = 0.0
                continue

            # Get reviews for this result
            result_reviews = [r for r in reviews if r.target_task_id == result.task_id]
            if result_reviews:
                avg_score = sum(r.score for r in result_reviews) / len(result_reviews)
            else:
                avg_score = 0.5  # Default score if no reviews

            # Factor in execution time (faster is better)
            time_factor = 1.0 / (result.execution_time_ms + 1.0)

            # Combined score
            scores[result.task_id] = avg_score * 0.8 + time_factor * 0.2

        # Return result with highest score
        best_task_id = max(scores.keys(), key=lambda k: scores[k]) if scores else None
        if best_task_id:
            return next((r for r in report.results if r.task_id == best_task_id), None)

        return report.best_result
