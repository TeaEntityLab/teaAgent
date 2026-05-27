"""Tool detection for LSP/static analysis tools.

This module detects available validation tools in the project.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Set


def detect_available_tools(root: Path) -> Set[str]:
    """Detect available LSP/static analysis tools in the project.
    
    Args:
        root: The workspace root directory
        
    Returns:
        Set of available tool names (e.g., {'ruff', 'mypy', 'tsc', 'eslint'})
    """
    available = set()
    
    # Check for Python tools
    if shutil.which("ruff"):
        available.add("ruff")
    if shutil.which("mypy"):
        available.add("mypy")
    
    # Check for TypeScript/JavaScript tools
    if shutil.which("tsc"):
        available.add("tsc")
    if shutil.which("eslint"):
        available.add("eslint")
    
    # Check for project-specific configuration files
    if (root / "pyproject.toml").exists():
        # Could be configured for ruff, mypy, etc.
        content = (root / "pyproject.toml").read_text()
        if "ruff" in content.lower():
            available.add("ruff")
        if "mypy" in content.lower():
            available.add("mypy")
    
    if (root / "tsconfig.json").exists():
        available.add("tsc")
    
    if (root / ".eslintrc").exists() or (root / ".eslintrc.json").exists() or (root / ".eslintrc.js").exists():
        available.add("eslint")
    
    return available


def get_tool_command(tool: str, file_path: Path) -> list[str]:
    """Get the command to run a validation tool.
    
    Args:
        tool: The tool name
        file_path: The file to validate
        
    Returns:
        Command as list of strings
    """
    if tool == "ruff":
        return ["ruff", "check", str(file_path)]
    elif tool == "mypy":
        return ["mypy", str(file_path)]
    elif tool == "tsc":
        return ["tsc", "--noEmit", str(file_path)]
    elif tool == "eslint":
        return ["eslint", str(file_path)]
    else:
        raise ValueError(f"Unknown tool: {tool}")
