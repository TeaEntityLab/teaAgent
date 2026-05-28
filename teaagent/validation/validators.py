"""LSP/static analysis validators.

This module provides validation runners for different tools.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from teaagent.validation.tool_detector import detect_available_tools, get_tool_command


@dataclass
class ValidationError:
    """A validation error with location and message."""

    file_path: str
    line_number: Optional[int]
    column: Optional[int]
    error_type: str
    message: str
    severity: str  # "error" or "warning"


@dataclass
class ValidationResult:
    """Result of running validation on a file."""

    tool: str
    passed: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]
    output: str

    def has_errors(self) -> bool:
        """Check if validation has errors."""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Check if validation has warnings."""
        return len(self.warnings) > 0


class ValidationRunner:
    """Runner for LSP/static analysis validation."""

    def __init__(self, root: Path, timeout: int = 30) -> None:
        """Initialize validation runner.

        Args:
            root: The workspace root directory
            timeout: Timeout in seconds for each validation
        """
        self.root = Path(root).resolve()
        self.timeout = timeout
        self.available_tools = detect_available_tools(root)

    def validate_file(self, file_path: Path) -> List[ValidationResult]:
        """Validate a file with all available tools.

        Args:
            file_path: The file to validate

        Returns:
            List of validation results for each tool
        """
        results = []

        for tool in self.available_tools:
            try:
                result = self._run_tool(tool, file_path)
                results.append(result)
            except Exception as exc:
                # Don't let one tool failure break validation
                import sys

                print(
                    f'[TeaAgent] Warning: {tool} validation failed: {exc}',
                    file=sys.stderr,
                )
                results.append(
                    ValidationResult(
                        tool=tool,
                        passed=False,
                        errors=[],
                        warnings=[],
                        output=str(exc),
                    )
                )

        return results

    def _run_tool(self, tool: str, file_path: Path) -> ValidationResult:
        """Run a specific validation tool.

        Args:
            tool: The tool name
            file_path: The file to validate

        Returns:
            ValidationResult
        """
        command = get_tool_command(tool, file_path)

        try:
            result = subprocess.run(
                command,
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            # Parse output
            errors, warnings = self._parse_output(tool, result.stdout, result.stderr)

            return ValidationResult(
                tool=tool,
                passed=result.returncode == 0,
                errors=errors,
                warnings=warnings,
                output=result.stdout + result.stderr,
            )
        except subprocess.TimeoutExpired:
            return ValidationResult(
                tool=tool,
                passed=False,
                errors=[],
                warnings=[],
                output=f'Validation timed out after {self.timeout}s',
            )
        except FileNotFoundError:
            return ValidationResult(
                tool=tool,
                passed=False,
                errors=[],
                warnings=[],
                output=f'Tool not found: {tool}',
            )

    def _parse_output(
        self, tool: str, stdout: str, stderr: str
    ) -> tuple[List[ValidationError], List[ValidationError]]:
        """Parse tool output into errors and warnings.

        Args:
            tool: The tool name
            stdout: Standard output
            stderr: Standard error

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []
        output = stdout + stderr

        # Simple parsing for common tools
        # In production, this would be more sophisticated
        lines = output.split('\n')

        for line in lines:
            if not line.strip():
                continue

            # Try to extract line number and message
            # Format varies by tool, this is a simplified parser
            if ':' in line:
                parts = line.split(':', 3)
                if len(parts) >= 2:
                    try:
                        line_num = int(parts[1])
                        message = parts[-1] if len(parts) > 2 else line

                        # Determine severity
                        severity = 'error'
                        if 'warning' in message.lower() or 'warn' in message.lower():
                            severity = 'warning'

                        error = ValidationError(
                            file_path=str(self.root),
                            line_number=line_num,
                            column=None,
                            error_type=tool,
                            message=message.strip(),
                            severity=severity,
                        )

                        if severity == 'error':
                            errors.append(error)
                        else:
                            warnings.append(error)
                    except ValueError:
                        # Not a line number, skip
                        pass

        return errors, warnings
