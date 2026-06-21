"""Open Knowledge Format v0.1 bundle parsing and validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote, urlsplit

from teaagent.path_safety import resolve_contained_path

OKF_VERSION = '0.1'
DEFAULT_MAX_CONCEPT_BYTES = 1_048_576
DEFAULT_MAX_BUNDLE_FILES = 10_000
_FRONTMATTER_RE = re.compile(
    r'\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)(.*)\Z',
    re.DOTALL,
)
_MARKDOWN_LINK_RE = re.compile(r'(?<!!)\[[^\]]+\]\(([^)]+)\)')
_INDEX_ENTRY_RE = re.compile(r'^\s*[-*]\s+\[[^\]]+\]\([^)]+\)', re.MULTILINE)
_DATE_HEADING_RE = re.compile(r'^##\s+(\d{4}-\d{2}-\d{2})\s*$', re.MULTILINE)

FindingSeverity = Literal['error', 'warning']


@dataclass(frozen=True)
class OkfFinding:
    """One conformance or safety finding for an OKF bundle."""

    severity: FindingSeverity
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            'severity': self.severity,
            'code': self.code,
            'path': self.path,
            'message': self.message,
        }


@dataclass(frozen=True)
class OkfConcept:
    """A parsed OKF concept document."""

    concept_id: str
    path: str
    metadata: dict[str, Any]
    body: str

    def to_dict(self, *, include_body: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'concept_id': self.concept_id,
            'path': self.path,
            'metadata': dict(self.metadata),
        }
        if include_body:
            payload['body'] = self.body
        return payload


@dataclass(frozen=True)
class OkfBundle:
    """Parsed bundle plus deterministic conformance findings."""

    root: Path
    version: str | None
    concepts: tuple[OkfConcept, ...]
    findings: tuple[OkfFinding, ...]

    @property
    def conformant(self) -> bool:
        return not any(finding.severity == 'error' for finding in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            'root': str(self.root),
            'version': self.version,
            'conformant': self.conformant,
            'concept_count': len(self.concepts),
            'concepts': [
                concept.to_dict(include_body=False) for concept in self.concepts
            ],
            'findings': [finding.to_dict() for finding in self.findings],
        }


def _load_yaml_mapping(text: str) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError(
            'OKF support requires PyYAML; install teaagent[yaml]'
        ) from exc
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f'invalid YAML frontmatter: {exc}') from exc
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ValueError('frontmatter must be a YAML mapping')
    normalized = _normalize_yaml_value(parsed)
    if not isinstance(normalized, dict):
        raise ValueError('frontmatter must be a YAML mapping')
    return normalized


def _normalize_yaml_value(value: Any) -> Any:
    """Convert safe YAML values to deterministic JSON-compatible values."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError('frontmatter numbers must be finite')
        return value
    if isinstance(value, datetime):
        return value.isoformat().replace('+00:00', 'Z')
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [_normalize_yaml_value(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError('frontmatter mapping keys must be strings')
            normalized[key] = _normalize_yaml_value(item)
        return normalized
    raise ValueError(
        f'frontmatter contains unsupported YAML value: {type(value).__name__}'
    )


def _split_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return None, text
    return _load_yaml_mapping(match.group(1)), match.group(2)


def _read_text(path: Path, *, max_bytes: int) -> str:
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(f'document exceeds {max_bytes} bytes')
    try:
        return path.read_text(encoding='utf-8')
    except UnicodeDecodeError as exc:
        raise ValueError('document must be UTF-8') from exc


def _finding(
    severity: FindingSeverity, code: str, path: str, message: str
) -> OkfFinding:
    return OkfFinding(severity=severity, code=code, path=path, message=message)


def _validate_index(
    *,
    path: str,
    metadata: dict[str, Any] | None,
    body: str,
    is_root: bool,
) -> tuple[list[OkfFinding], str | None]:
    findings: list[OkfFinding] = []
    version: str | None = None
    if metadata is not None:
        if not is_root:
            findings.append(
                _finding(
                    'error',
                    'index_frontmatter_not_allowed',
                    path,
                    'only the bundle-root index.md may contain frontmatter',
                )
            )
        else:
            raw_version = metadata.get('okf_version')
            if raw_version is not None and not isinstance(raw_version, str):
                findings.append(
                    _finding(
                        'error',
                        'invalid_version',
                        path,
                        'okf_version must be a quoted string',
                    )
                )
            elif isinstance(raw_version, str):
                version = raw_version.strip()
                if version != OKF_VERSION:
                    findings.append(
                        _finding(
                            'warning',
                            'unsupported_version',
                            path,
                            f'consumer supports OKF {OKF_VERSION}, found {version}',
                        )
                    )
    if not re.search(r'^#\s+\S', body, re.MULTILINE):
        findings.append(
            _finding(
                'error', 'invalid_index', path, 'index.md requires a section heading'
            )
        )
    if not _INDEX_ENTRY_RE.search(body):
        findings.append(
            _finding(
                'error',
                'invalid_index',
                path,
                'index.md requires at least one markdown list entry',
            )
        )
    return findings, version


def _validate_log(
    *, path: str, metadata: dict[str, Any] | None, body: str
) -> list[OkfFinding]:
    findings: list[OkfFinding] = []
    if metadata is not None:
        findings.append(
            _finding(
                'error',
                'log_frontmatter_not_allowed',
                path,
                'log.md must not contain frontmatter',
            )
        )
    if not re.search(r'^#\s+\S', body, re.MULTILINE):
        findings.append(
            _finding('error', 'invalid_log', path, 'log.md requires a title heading')
        )
    date_values = _DATE_HEADING_RE.findall(body)
    parsed_dates: list[date] = []
    for value in date_values:
        try:
            parsed_dates.append(date.fromisoformat(value))
        except ValueError:
            findings.append(
                _finding('error', 'invalid_log_date', path, f'invalid date: {value}')
            )
    if not parsed_dates:
        findings.append(
            _finding(
                'error',
                'invalid_log',
                path,
                'log.md requires at least one ISO 8601 date heading',
            )
        )
    elif parsed_dates != sorted(parsed_dates, reverse=True):
        findings.append(
            _finding(
                'error',
                'invalid_log_order',
                path,
                'log.md date headings must be newest first',
            )
        )
    if not re.search(r'^\s*[-*]\s+\S', body, re.MULTILINE):
        findings.append(
            _finding('error', 'invalid_log', path, 'log.md requires a list entry')
        )
    return findings


def _link_target(raw_target: str) -> str | None:
    target = raw_target.strip()
    if target.startswith('<'):
        closing = target.find('>')
        if closing < 0:
            return target
        target = target[1:closing].strip()
    else:
        target = target.split(maxsplit=1)[0]
    if not target or target.startswith('#'):
        return None
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None
    return unquote(parsed.path)


def _validate_links(
    *, bundle_root: Path, document_path: Path, body: str, display_path: str
) -> list[OkfFinding]:
    findings: list[OkfFinding] = []
    document_parent = document_path.parent.relative_to(bundle_root)
    for match in _MARKDOWN_LINK_RE.finditer(body):
        target = _link_target(match.group(1))
        if target is None:
            continue
        if '\\' in target:
            findings.append(
                _finding(
                    'error',
                    'unsafe_link',
                    display_path,
                    f'non-portable link target ignored: {target}',
                )
            )
            continue
        relative_target = Path(target.lstrip('/'))
        if not target.startswith('/'):
            relative_target = document_parent / relative_target
        try:
            resolved = resolve_contained_path(bundle_root, relative_target)
        except ValueError as exc:
            findings.append(
                _finding('error', 'unsafe_link', display_path, f'{target}: {exc}')
            )
            continue
        if not resolved.exists():
            findings.append(
                _finding(
                    'warning',
                    'broken_link',
                    display_path,
                    f'link target does not exist: {target}',
                )
            )
    return findings


def validate_okf_bundle(
    workspace_root: str | Path,
    bundle_path: str | Path = 'knowledge',
    *,
    max_concept_bytes: int = DEFAULT_MAX_CONCEPT_BYTES,
    max_bundle_files: int = DEFAULT_MAX_BUNDLE_FILES,
) -> OkfBundle:
    """Parse and validate an OKF v0.1 bundle contained by a workspace."""
    if max_concept_bytes < 1 or max_bundle_files < 1:
        raise ValueError('OKF size limits must be positive')
    bundle_root = resolve_contained_path(
        workspace_root, bundle_path, must_exist=True, require_directory=True
    )
    tree_paths: list[Path] = []
    for path in bundle_root.rglob('*'):
        tree_paths.append(path)
        if len(tree_paths) > max_bundle_files:
            finding = _finding(
                'error',
                'bundle_too_large',
                '.',
                f'bundle contains more than {max_bundle_files} entries',
            )
            return OkfBundle(bundle_root, None, (), (finding,))
    tree_paths.sort()
    markdown_paths = [
        path for path in tree_paths if path.name.endswith('.md') and not path.is_dir()
    ]

    concepts: list[OkfConcept] = []
    findings: list[OkfFinding] = [
        _finding(
            'error',
            'symlink_not_allowed',
            path.relative_to(bundle_root).as_posix(),
            'bundle entries must not be symbolic links',
        )
        for path in tree_paths
        if path.is_symlink()
    ]
    version: str | None = None
    for document_path in markdown_paths:
        display_path = document_path.relative_to(bundle_root).as_posix()
        if document_path.is_symlink():
            continue
        try:
            text = _read_text(document_path, max_bytes=max_concept_bytes)
            metadata, body = _split_frontmatter(text)
        except (OSError, RuntimeError, ValueError) as exc:
            findings.append(
                _finding('error', 'invalid_document', display_path, str(exc))
            )
            continue

        if document_path.name == 'index.md':
            index_findings, index_version = _validate_index(
                path=display_path,
                metadata=metadata,
                body=body,
                is_root=document_path.parent == bundle_root,
            )
            findings.extend(index_findings)
            if index_version is not None:
                version = index_version
        elif document_path.name == 'log.md':
            findings.extend(
                _validate_log(path=display_path, metadata=metadata, body=body)
            )
        else:
            if metadata is None:
                findings.append(
                    _finding(
                        'error',
                        'missing_frontmatter',
                        display_path,
                        'concept document requires YAML frontmatter',
                    )
                )
            else:
                concept_type = metadata.get('type')
                if not isinstance(concept_type, str) or not concept_type.strip():
                    findings.append(
                        _finding(
                            'error',
                            'missing_type',
                            display_path,
                            'concept frontmatter requires a non-empty type',
                        )
                    )
                else:
                    concepts.append(
                        OkfConcept(
                            concept_id=document_path.relative_to(bundle_root)
                            .with_suffix('')
                            .as_posix(),
                            path=display_path,
                            metadata=metadata,
                            body=body,
                        )
                    )
        findings.extend(
            _validate_links(
                bundle_root=bundle_root,
                document_path=document_path,
                body=body,
                display_path=display_path,
            )
        )

    if not markdown_paths:
        findings.append(
            _finding(
                'warning', 'empty_bundle', '.', 'bundle contains no markdown files'
            )
        )
    return OkfBundle(
        root=bundle_root,
        version=version,
        concepts=tuple(sorted(concepts, key=lambda concept: concept.concept_id)),
        findings=tuple(
            sorted(
                findings,
                key=lambda finding: (
                    finding.path,
                    finding.severity,
                    finding.code,
                    finding.message,
                ),
            )
        ),
    )


def get_okf_concept(
    workspace_root: str | Path,
    bundle_path: str | Path,
    concept_id: str,
) -> tuple[OkfBundle, OkfConcept]:
    """Return one concept from a conformant bundle by its concept ID."""
    bundle = validate_okf_bundle(workspace_root, bundle_path)
    if not bundle.conformant:
        raise ValueError('cannot read a concept from a non-conformant OKF bundle')
    normalized_id = concept_id.strip().removesuffix('.md')
    if not normalized_id or normalized_id in {'index', 'log'}:
        raise ValueError('concept_id must identify a non-reserved concept document')
    concept_path = resolve_contained_path(
        bundle.root,
        f'{normalized_id}.md',
        must_exist=True,
        require_file=True,
    )
    expected_path = concept_path.relative_to(bundle.root).as_posix()
    for concept in bundle.concepts:
        if concept.path == expected_path:
            return bundle, concept
    raise FileNotFoundError(f"OKF concept not found: '{concept_id}'")
