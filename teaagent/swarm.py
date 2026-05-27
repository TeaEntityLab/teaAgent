"""Multi-agent swarm orchestration for parallel task execution.

This module provides SwarmManager for coordinating multiple subagents
with OSSandbox isolation, enabling parallel experiment branches and
automated code review between subagents.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from teaagent.git_sandbox import GitBranchSandbox, GitSandboxResult


@dataclass(frozen=True)
class SubagentTask:
    """Task definition for a subagent."""
    task_id: str
    description: str
    context: dict[str, Any] = field(default_factory=dict)
    priority: int = 0


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
    recommendation: str = ""  # "approve", "reject", "request_changes"


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
                error="Git sandbox not available",
            )

        # Start sandbox branch
        sandbox_result = self._sandbox.start(auto_stash=True)
        if not sandbox_result.success:
            return SubagentResult(
                task_id=self._task.task_id,
                success=False,
                error=sandbox_result.error or "Failed to start sandbox",
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
            "task": self._task.description,
            "status": "completed",
            "files_modified": [],
            "changes_summary": "Mock execution",
        }

    def cleanup(self) -> None:
        """Cleanup sandbox branch after execution."""
        if self._sandbox.is_available():
            # Switch back to original branch
            if self._sandbox._original_branch:
                try:
                    import subprocess
                    subprocess.run(
                        ['git', 'checkout', self._sandbox._original_branch],
                        cwd=self._root,
                        capture_output=True,
                        check=True,
                    )
                except subprocess.CalledProcessError:
                    pass


class SwarmManager:
    """Orchestrates multiple subagents with parallel execution."""

    def __init__(self, root: str | Path, max_parallel: int = 3) -> None:
        self._root = Path(root).resolve()
        self._max_parallel = max_parallel
        self._subagents: list[Subagent] = []
        self._results: list[SubagentResult] = []

    def add_subagent(self, task: SubagentTask) -> None:
        """Add a subagent task to the swarm."""
        subagent = Subagent(task, self._root)
        self._subagents.append(subagent)

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

        # Find best result (simple heuristic: first successful result)
        best_result = next((r for r in results if r.success), None)

        return SwarmReport(
            total_subagents=len(self._subagents),
            successful_subagents=successful,
            failed_subagents=failed,
            results=results,
            code_reviews=[],  # Will be populated by code review phase
            best_result=best_result,
            total_execution_time_ms=total_time,
        )

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

    def _review_subagent(self, reviewer: SubagentResult, target: SubagentResult) -> CodeReview:
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
            findings=["Mock code review finding"],
            recommendation="approve",
        )

    def select_best_result(self, report: SwarmReport, reviews: list[CodeReview]) -> Optional[SubagentResult]:
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
        best_task_id = max(scores, key=scores.get) if scores else None
        if best_task_id:
            return next((r for r in report.results if r.task_id == best_task_id), None)
        
        return report.best_result
