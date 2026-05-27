"""Parallel executor for tournament subagents.

This module provides:
- Spawning and managing multiple subagent processes
- Resource limits and timeout handling
- Result collection from all agents
"""

from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


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
    
    def __init__(self, root: Path, timeout: int = 300) -> None:
        """Initialize parallel executor.
        
        Args:
            root: The workspace root directory
            timeout: Timeout in seconds for each agent
        """
        self.root = Path(root).resolve()
        self.timeout = timeout
        self.results: List[AgentResult] = []
    
    def execute_parallel(
        self,
        task: str,
        branches: List[str],
        approach_hints: List[str],
    ) -> List[AgentResult]:
        """Execute subagents in parallel on different branches.
        
        Args:
            task: The task description
            branches: List of branch names
            approach_hints: List of approach hints for each branch
            
        Returns:
            List of AgentResult from each agent
        """
        if len(branches) != len(approach_hints):
            raise ValueError("Branches and approach hints must have same length")
        
        # Execute in parallel using threads
        threads = []
        results_lock = threading.Lock()
        
        for i, (branch, hint) in enumerate(zip(branches, approach_hints)):
            thread = threading.Thread(
                target=self._execute_agent,
                args=(task, branch, hint, i, results_lock),
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=self.timeout + 10)
        
        return self.results
    
    def _execute_agent(
        self,
        task: str,
        branch: str,
        hint: str,
        index: int,
        results_lock: threading.Lock,
    ) -> None:
        """Execute a single agent on a branch.
        
        Args:
            task: The task description
            branch: The branch name
            hint: The approach hint
            index: The agent index
            results_lock: Lock for thread-safe result storage
        """
        start_time = time.time()
        
        try:
            # Switch to branch
            subprocess.run(
                ['git', 'checkout', branch],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=True,
            )
            
            # Run agent with approach hint
            # In a full implementation, this would spawn a subagent process
            # For now, we simulate the execution
            command = [
                'teaagent', 'run',
                f'{task} (approach: {hint})',
                '--root', str(self.root),
            ]
            
            result = subprocess.run(
                command,
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            
            success = result.returncode == 0
            output = result.stdout
            error = result.stderr if result.stderr else None
            
        except subprocess.TimeoutExpired:
            success = False
            output = ""
            error = f"Agent execution timed out after {self.timeout}s"
        except subprocess.CalledProcessError as exc:
            success = False
            output = exc.stdout
            error = exc.stderr
        except Exception as exc:
            success = False
            output = ""
            error = str(exc)
        
        execution_time = time.time() - start_time
        
        # Store result
        agent_result = AgentResult(
            approach_id=f"opt{index+1}",
            branch_name=branch,
            success=success,
            output=output,
            error=error,
            execution_time=execution_time,
            metadata={},
        )
        
        with results_lock:
            self.results.append(agent_result)
