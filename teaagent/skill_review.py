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
        _check_dangerous_call(node, self.calls_found)
        self.generic_visit(node)


def _check_dangerous_call(node: ast.Call, calls_found: set[str]) -> None:
    if isinstance(node.func, ast.Name):
        func_name = node.func.id
        if func_name in DANGEROUS_CALLS:
            calls_found.add(func_name)
    elif isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name):
            full_name = f'{node.func.value.id}.{node.func.attr}'
            if full_name in DANGEROUS_CALLS or node.func.attr in DANGEROUS_CALLS:
                calls_found.add(full_name)


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


def _report_import_findings(
    imports_found: set[str],
    file_path: Path,
) -> SkillReviewFinding | None:
    if not imports_found:
        return None
    return SkillReviewFinding(
        'warning',
        f'Python file imports potentially dangerous modules: {", ".join(sorted(imports_found))}. '
        'Review for network access, file operations, or code execution risks.',
    )


def _report_call_findings(
    calls_found: set[str],
) -> SkillReviewFinding | None:
    if not calls_found:
        return None
    return SkillReviewFinding(
        'warning',
        f'Python file calls potentially dangerous functions: {", ".join(sorted(calls_found))}. '
        'Review for dynamic code execution or system operation risks.',
    )


def _analyze_python_file_for_dangerous_patterns(
    file_path: Path,
) -> list[SkillReviewFinding]:
    findings: list[SkillReviewFinding] = []

    try:
        source = file_path.read_text(encoding='utf-8')
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, OSError) as exc:
        logger.warning(f'Failed to parse {file_path}: {exc}')
        return findings

    visitor = DangerousPatternVisitor(findings, file_path)
    visitor.visit(tree)

    import_finding = _report_import_findings(visitor.imports_found, file_path)
    if import_finding is not None:
        findings.append(import_finding)

    call_finding = _report_call_findings(visitor.calls_found)
    if call_finding is not None:
        findings.append(call_finding)

    return findings


def _check_skill_frontmatter(text: str, lines: list[str]) -> list[SkillReviewFinding]:
    findings: list[SkillReviewFinding] = []
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
    return findings


def _check_skill_content_patterns(
    text: str, lines: list[str], max_skill_md_lines: int, *, installed: bool = False
) -> list[SkillReviewFinding]:
    findings: list[SkillReviewFinding] = []
    if len(lines) > max_skill_md_lines:
        oversize_severity = 'error' if installed else 'warning'
        findings.append(
            SkillReviewFinding(
                oversize_severity,
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
    return findings


def review_skill(
    skill_path: Path, *, max_skill_md_lines: int = 80, installed: bool = False
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
    findings.extend(_check_skill_frontmatter(text, lines))
    findings.extend(
        _check_skill_content_patterns(
            text, lines, max_skill_md_lines, installed=installed
        )
    )

    if skill_path.is_dir():
        _analyze_skill_python_files(skill_path, findings)

    return SkillReviewResult(skill_path=skill_file, findings=findings)


def _analyze_skill_python_files(
    skill_path: Path, findings: list[SkillReviewFinding]
) -> None:
    for py_file in skill_path.rglob('*.py'):
        if py_file.name == 'SKILL.md':
            continue
        try:
            py_findings = _analyze_python_file_for_dangerous_patterns(py_file)
            findings.extend(py_findings)
        except Exception as exc:
            logger.warning(f'Error analyzing {py_file}: {exc}')
