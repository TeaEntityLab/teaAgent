from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass
from pathlib import Path

EXTERNAL_COMMAND_PATTERNS = (
    re.compile(r'\b(curl|wget|ssh|scp|nc)\b'),
    re.compile(r'https?://'),
)
BLOCKLIST_PATTERNS = (
    re.compile(r'ignore\s+(all\s+)?(previous|prior)\s+instructions', re.IGNORECASE),
    re.compile(r'print\s+all\s+environment\s+variables', re.IGNORECASE),
    re.compile(
        r'\b(export|echo)\s+.*(api[_-]?key|token|secret|password)\b', re.IGNORECASE
    ),
    re.compile(r'\brm\s+-rf\b', re.IGNORECASE),
)

# Dangerous imports that could indicate network access or system operations
DANGEROUS_IMPORTS = {
    'requests',
    'urllib',
    'urllib2',
    'urllib3',
    'httpx',
    'aiohttp',
    'socket',
    'subprocess',
    'os',
    'sys',
    'shutil',
    'pathlib',
    'pickle',
    'marshal',
    'eval',
    'exec',
    'compile',
}

# Potentially dangerous function calls
DANGEROUS_CALLS = {
    'eval',
    'exec',
    'compile',
    '__import__',
    'open',
    'subprocess.run',
    'subprocess.call',
    'subprocess.Popen',
    'os.system',
    'os.popen',
    'os.spawn',
}

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillReviewFinding:
    severity: str
    message: str


@dataclass(frozen=True)
class SkillReviewResult:
    skill_path: Path
    findings: list[SkillReviewFinding]

    @property
    def passed(self) -> bool:
        return not any(finding.severity == 'error' for finding in self.findings)


def _analyze_python_file_for_dangerous_patterns(
    file_path: Path,
) -> list[SkillReviewFinding]:
    """Analyze Python files for dangerous imports and function calls using AST."""
    findings: list[SkillReviewFinding] = []

    try:
        source = file_path.read_text(encoding='utf-8')
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, OSError) as exc:
        logger.warning(f'Failed to parse {file_path}: {exc}')
        return findings

    class DangerousPatternVisitor(ast.NodeVisitor):
        def __init__(self, findings: list[SkillReviewFinding], file_path: Path):
            self.findings = findings
            self.file_path = file_path
            self.imports_found: set[str] = set()
            self.calls_found: set[str] = set()

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                module_name = alias.name.split('.')[0]
                if module_name in DANGEROUS_IMPORTS:
                    self.imports_found.add(module_name)
            self.generic_visit(node)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            if node.module:
                module_name = node.module.split('.')[0]
                if module_name in DANGEROUS_IMPORTS:
                    self.imports_found.add(module_name)
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
                if func_name in DANGEROUS_CALLS:
                    self.calls_found.add(func_name)
            elif isinstance(node.func, ast.Attribute):
                # Handle calls like subprocess.run
                if isinstance(node.func.value, ast.Name):
                    full_name = f'{node.func.value.id}.{node.func.attr}'
                    if (
                        full_name in DANGEROUS_CALLS
                        or node.func.attr in DANGEROUS_CALLS
                    ):
                        self.calls_found.add(full_name)
            self.generic_visit(node)

    visitor = DangerousPatternVisitor(findings, file_path)
    visitor.visit(tree)

    # Report findings
    if visitor.imports_found:
        findings.append(
            SkillReviewFinding(
                'warning',
                f'Python file imports potentially dangerous modules: {", ".join(sorted(visitor.imports_found))}. '
                'Review for network access, file operations, or code execution risks.',
            )
        )

    if visitor.calls_found:
        findings.append(
            SkillReviewFinding(
                'warning',
                f'Python file calls potentially dangerous functions: {", ".join(sorted(visitor.calls_found))}. '
                'Review for dynamic code execution or system operation risks.',
            )
        )

    return findings


def review_skill(
    skill_path: Path, *, max_skill_md_lines: int = 80
) -> SkillReviewResult:
    skill_file = skill_path / 'SKILL.md' if skill_path.is_dir() else skill_path
    findings: list[SkillReviewFinding] = []
    if not skill_file.exists():
        return SkillReviewResult(
            skill_path=skill_file,
            findings=[SkillReviewFinding('error', 'SKILL.md is missing')],
        )

    text = skill_file.read_text(encoding='utf-8')
    lines = text.splitlines()
    if not lines or lines[0] != '---':
        findings.append(
            SkillReviewFinding('error', 'SKILL.md must start with YAML frontmatter')
        )
    if 'name:' not in text:
        findings.append(
            SkillReviewFinding('error', 'SKILL.md frontmatter must include name')
        )
    if 'description:' not in text:
        findings.append(
            SkillReviewFinding('error', 'SKILL.md frontmatter must include description')
        )
    if len(lines) > max_skill_md_lines:
        findings.append(
            SkillReviewFinding(
                'warning',
                f'SKILL.md has {len(lines)} lines; prefer Progressive Disclosure',
            )
        )
    for pattern in EXTERNAL_COMMAND_PATTERNS:
        if pattern.search(text):
            findings.append(
                SkillReviewFinding(
                    'warning',
                    'SKILL.md references external network access; review supply-chain risk',
                )
            )
            break
    if 'REFERENCE.md' not in text and len(lines) > 40:
        findings.append(
            SkillReviewFinding(
                'warning',
                'Long skill should reference REFERENCE.md for Progressive Disclosure',
            )
        )
    for pattern in BLOCKLIST_PATTERNS:
        if pattern.search(text):
            findings.append(
                SkillReviewFinding(
                    'error',
                    'SKILL.md contains blocked instruction pattern (potential unsafe persistence)',
                )
            )
            break

    # AST-based analysis of Python files in skill directory
    if skill_path.is_dir():
        for py_file in skill_path.rglob('*.py'):
            # Skip the SKILL.md file itself if it got picked up
            if py_file.name == 'SKILL.md':
                continue
            try:
                py_findings = _analyze_python_file_for_dangerous_patterns(py_file)
                findings.extend(py_findings)
            except Exception as exc:
                logger.warning(f'Error analyzing {py_file}: {exc}')

    return SkillReviewResult(skill_path=skill_file, findings=findings)
