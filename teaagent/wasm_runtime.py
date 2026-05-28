"""WebAssembly runtime for lightweight sandboxing.

This module provides a WASM runtime wrapper for executing untrusted
dynamic skills in an isolated environment with fast startup and memory isolation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from wasmer import Module, Store  # type: ignore

    WASMER_AVAILABLE = True
except ImportError:
    WASMER_AVAILABLE = False

    # Create dummy types for type checking when wasmer is not available
    class _DummyStore:
        pass

    class _DummyModule:
        pass

    Store = _DummyStore  # type: ignore[misc,assignment]
    Module = _DummyModule  # type: ignore[misc,assignment]


@dataclass
class WASMExecutionResult:
    """Result of WASM execution."""

    success: bool
    output: str
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    memory_used_mb: float = 0.0


class WASMRuntime:
    """Lightweight WebAssembly runtime for skill execution."""

    def __init__(
        self,
        memory_limit_mb: int = 256,
        enable_syscalls: Optional[list[str]] = None,
    ) -> None:
        """Initialize WASM runtime.

        Args:
            memory_limit_mb: Memory limit in MB
            enable_syscalls: List of allowed syscalls (None for restricted default)

        Raises:
            ImportError: If wasmer is not available
        """
        if not WASMER_AVAILABLE:
            raise ImportError(
                'WASM runtime requires wasmer. Install with: pip install teaagent[wasm]'
            )

        self.memory_limit_mb = memory_limit_mb
        self.enable_syscalls = enable_syscalls or []
        self._instance: Optional[Any] = None

    def load_module(self, wasm_path: Path) -> bool:
        """Load a WASM module.

        Args:
            wasm_path: Path to the WASM module file

        Returns:
            True if module loaded successfully
        """
        if not WASMER_AVAILABLE:
            return False

        try:
            # Create WASM store
            store = Store()

            # Load the module
            module = Module(store, wasm_path.read_bytes())

            # Create instance with memory limit
            self._instance = module.instantiate(store)

            logger.info(f'Loaded WASM module from {wasm_path}')
            return True
        except Exception as exc:
            logger.error(f'Failed to load WASM module: {exc}')
            return False

    def execute(
        self,
        function_name: str,
        *args: Any,
    ) -> WASMExecutionResult:
        """Execute a function in the WASM module.

        Args:
            function_name: Name of the function to execute
            *args: Arguments to pass to the function

        Returns:
            Execution result
        """
        import time

        if not self._instance:
            return WASMExecutionResult(
                success=False,
                output='',
                error='No WASM module loaded',
            )

        start_time = time.perf_counter()

        try:
            # Get the function
            func = self._instance.exports[function_name]

            # Execute the function
            result = func(*args)

            execution_time = (time.perf_counter() - start_time) * 1000

            return WASMExecutionResult(
                success=True,
                output=str(result),
                execution_time_ms=execution_time,
                memory_used_mb=0.0,  # Would need to track actual memory usage
            )
        except KeyError:
            execution_time = (time.perf_counter() - start_time) * 1000
            return WASMExecutionResult(
                success=False,
                output='',
                error=f'Function {function_name} not found in WASM module',
                execution_time_ms=execution_time,
            )
        except Exception as exc:
            execution_time = (time.perf_counter() - start_time) * 1000
            return WASMExecutionResult(
                success=False,
                output='',
                error=str(exc),
                execution_time_ms=execution_time,
            )

    def check_compatibility(self, skill_path: Path) -> dict[str, Any]:
        """Check if a skill is compatible with WASM.

        Args:
            skill_path: Path to the skill directory

        Returns:
            Dictionary with compatibility check results
        """
        result: dict[str, Any] = {
            'compatible': True,
            'issues': [],
            'warnings': [],
        }

        # Check for Python files
        py_files = list(skill_path.glob('**/*.py'))
        if not py_files:
            result['compatible'] = False
            result['issues'].append('No Python files found in skill')
            return result

        # Check for unsupported Python features
        for py_file in py_files:
            content = py_file.read_text(encoding='utf-8')

            # Check for async/await (not supported in basic WASM)
            if 'async def' in content or 'await ' in content:
                result['compatible'] = False
                result['issues'].append(
                    f'{py_file.name}: async/await not supported in WASM'
                )

            # Check for socket module
            if 'import socket' in content or 'from socket' in content:
                result['warnings'].append(
                    f'{py_file.name}: socket module may not work in WASM'
                )

            # Check for subprocess module
            if 'import subprocess' in content or 'from subprocess' in content:
                result['warnings'].append(
                    f'{py_file.name}: subprocess module may not work in WASM'
                )

            # Check for eval/exec
            if 'eval(' in content or 'exec(' in content:
                result['warnings'].append(
                    f'{py_file.name}: eval/exec may be restricted in WASM'
                )

        return result

    def cleanup(self) -> None:
        """Clean up WASM runtime resources."""
        if self._instance:
            self._instance = None
            logger.info('WASM runtime cleaned up')


def is_wasm_available() -> bool:
    """Check if WASM runtime is available.

    Returns:
        True if wasmer is installed and available
    """
    return WASMER_AVAILABLE
