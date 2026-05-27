"""Tournament-style parallel execution and comparison.

This module provides:
- Parallel git sandbox branch creation
- Multi-agent parallel execution
- Benchmarking and comparison
- Approach recommendation
"""

from __future__ import annotations

from teaagent.tournament.branch_manager import TournamentBranchManager
from teaagent.tournament.hint_generator import ApproachHintGenerator
from teaagent.tournament.parallel_executor import ParallelExecutor
from teaagent.tournament.benchmark import BenchmarkRunner
from teaagent.tournament.comparator import TournamentComparator

__all__ = [
    "TournamentBranchManager",
    "ApproachHintGenerator",
    "ParallelExecutor",
    "BenchmarkRunner",
    "TournamentComparator",
]
