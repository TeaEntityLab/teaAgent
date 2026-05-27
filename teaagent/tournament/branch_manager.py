"""Tournament branch manager for parallel sandbox execution.

This module provides:
- Creation of isolated git sandbox branches
- Branch naming and metadata management
- Cleanup of tournament branches
"""

from __future__ import annotations

import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class TournamentBranch:
    """Metadata for a tournament branch."""
    
    branch_name: str
    approach_id: str
    approach_hint: str
    created_at: float


class TournamentBranchManager:
    """Manager for tournament git sandbox branches."""
    
    def __init__(self, root: Path) -> None:
        """Initialize tournament branch manager.
        
        Args:
            root: The workspace root directory
        """
        self.root = Path(root).resolve()
        self.branches: List[TournamentBranch] = []
    
    def create_branches(self, count: int, approach_hints: List[str]) -> List[TournamentBranch]:
        """Create isolated git sandbox branches for tournament.
        
        Args:
            count: Number of branches to create
            approach_hints: List of approach hints for each branch
            
        Returns:
            List of TournamentBranch metadata
        """
        if count != len(approach_hints):
            raise ValueError("Number of branches must match number of approach hints")
        
        # Check disk space
        self._check_disk_space(count)
        
        # Create branches
        timestamp = int(__import__('time').time())
        created_branches = []
        
        for i in range(count):
            branch_name = f"tournament-{timestamp}-opt{i+1}"
            approach_id = f"opt{i+1}"
            approach_hint = approach_hints[i]
            
            # Create branch
            self._create_git_branch(branch_name)
            
            branch = TournamentBranch(
                branch_name=branch_name,
                approach_id=approach_id,
                approach_hint=approach_hint,
                created_at=__import__('time').time(),
            )
            created_branches.append(branch)
            self.branches.append(branch)
        
        return created_branches
    
    def _create_git_branch(self, branch_name: str) -> None:
        """Create a new git branch from current HEAD.
        
        Args:
            branch_name: Name of the branch to create
        """
        try:
            subprocess.run(
                ['git', 'checkout', '-b', branch_name],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Failed to create branch {branch_name}: {exc.stderr}")
    
    def cleanup_branches(self) -> None:
        """Delete all tournament branches and return to original branch."""
        if not self.branches:
            return
        
        # Return to main branch
        try:
            subprocess.run(
                ['git', 'checkout', 'main'],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=False,
            )
        except subprocess.CalledProcessError:
            pass
        
        # Delete tournament branches
        for branch in self.branches:
            try:
                subprocess.run(
                    ['git', 'branch', '-D', branch.branch_name],
                    cwd=self.root,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except subprocess.CalledProcessError:
                pass
        
        self.branches.clear()
    
    def _check_disk_space(self, count: int) -> None:
        """Check if there's enough disk space for tournament branches.
        
        Args:
            count: Number of branches to create
            
        Raises:
            RuntimeError: If insufficient disk space
        """
        import shutil
        
        # Estimate required space (1GB per branch)
        required_gb = count * 1
        available_gb = shutil.disk_usage(self.root).free / (1024**3)
        
        if available_gb < required_gb:
            raise RuntimeError(
                f"Insufficient disk space for {count} branches. "
                f"Required: {required_gb}GB, Available: {available_gb:.1f}GB"
            )
