"""H4 policy/RBAC coverage-completeness evidence (ADR-0031 criterion 2).

This module prepares the second ADR-0031 promotion evidence item: every enabled
policy and every RBAC role must have declared allow-side and deny-side test
coverage before any shadow-to-enforce promotion. It inventories the current
workspace stores and compares them with the H4 section of the claim-to-test
traceability matrix.

Authority boundary: this is an evidence checker only. It does not run tests, does
not decide whether test behavior is sufficient, does not flip H4 modes, and does
not promote policy/RBAC enforcement. Missing or stale declarations are reported
as gaps for a human/operator to resolve.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from teaagent.governance.policy_engine import PolicyStore
from teaagent.governance.rbac import RoleStore

H4_COVERAGE_SECTION = 'h4_policy_rbac_coverage'
CoverageKind = Literal['policy', 'role']


@dataclass(frozen=True)
class H4CoverageDeclaration:
    """Declared allow/deny coverage for one policy or RBAC role."""

    kind: CoverageKind
    item_id: str
    allow_tests: tuple[str, ...]
    deny_tests: tuple[str, ...]
    note: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'kind': self.kind,
            'id': self.item_id,
            'allow_tests': list(self.allow_tests),
            'deny_tests': list(self.deny_tests),
            'note': self.note,
        }


@dataclass(frozen=True)
class H4CoverageItem:
    """Inventory item discovered from the current workspace store."""

    kind: CoverageKind
    item_id: str
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'kind': self.kind,
            'id': self.item_id,
            'name': self.name,
            'metadata': self.metadata,
        }


@dataclass(frozen=True)
class H4CoverageGap:
    """Actionable gap in the H4 coverage evidence packet."""

    kind: CoverageKind
    item_id: str
    issue: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'kind': self.kind,
            'id': self.item_id,
            'issue': self.issue,
            'detail': self.detail,
        }


@dataclass(frozen=True)
class H4CoverageReport:
    """Coverage-completeness evidence bundle for ADR-0031 criterion 2."""

    root: str
    matrix_path: str
    policies: list[H4CoverageItem]
    roles: list[H4CoverageItem]
    policy_declarations: list[H4CoverageDeclaration]
    role_declarations: list[H4CoverageDeclaration]
    gaps: list[H4CoverageGap]

    @property
    def ok(self) -> bool:
        return not self.gaps

    def to_dict(self) -> dict[str, Any]:
        return {
            'criterion': 'ADR-0031 criterion 2 — coverage completeness',
            'root': self.root,
            'matrix_path': self.matrix_path,
            'ok': self.ok,
            'policy_count': len(self.policies),
            'role_count': len(self.roles),
            'policy_declaration_count': len(self.policy_declarations),
            'role_declaration_count': len(self.role_declarations),
            'policies': [item.to_dict() for item in self.policies],
            'roles': [item.to_dict() for item in self.roles],
            'policy_declarations': [d.to_dict() for d in self.policy_declarations],
            'role_declarations': [d.to_dict() for d in self.role_declarations],
            'gaps': [gap.to_dict() for gap in self.gaps],
            'note': (
                'Evidence only: this checker verifies declarations and test-file '
                'references. It does not run tests, certify test semantics, or flip H4 modes.'
            ),
        }


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f'H4 coverage matrix not found: {path}')
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - PyYAML is present in CI/dev envs.
        raise RuntimeError('H4 coverage matrix parsing requires PyYAML') from exc
    try:
        parsed = yaml.safe_load(path.read_text(encoding='utf-8'))
    except yaml.YAMLError as exc:
        raise ValueError(f'invalid YAML in {path}: {exc}') from exc
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ValueError(f'H4 coverage matrix must be a YAML mapping: {path}')
    return parsed


def _as_test_tuple(value: Any, *, field_name: str, item_id: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f'{item_id}.{field_name} must be a list of test references')
    refs: list[str] = []
    for ref in value:
        if not isinstance(ref, str) or not ref.strip():
            raise ValueError(
                f'{item_id}.{field_name} contains a non-string test reference'
            )
        refs.append(ref.strip())
    return tuple(refs)


def _parse_declarations(
    entries: Any, *, kind: CoverageKind, id_key: str
) -> list[H4CoverageDeclaration]:
    if entries is None:
        return []
    if not isinstance(entries, list):
        raise ValueError(f'{H4_COVERAGE_SECTION}.{kind}s must be a list')
    out: list[H4CoverageDeclaration] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f'{H4_COVERAGE_SECTION}.{kind}s entries must be mappings')
        item_id = entry.get(id_key)
        if not isinstance(item_id, str) or not item_id.strip():
            raise ValueError(f'{H4_COVERAGE_SECTION}.{kind}s entry missing {id_key}')
        item_id = item_id.strip()
        if item_id in seen:
            raise ValueError(f'duplicate H4 {kind} coverage declaration: {item_id}')
        seen.add(item_id)
        note = entry.get('note', '')
        if note is None:
            note = ''
        if not isinstance(note, str):
            raise ValueError(f'{item_id}.note must be a string when present')
        out.append(
            H4CoverageDeclaration(
                kind=kind,
                item_id=item_id,
                allow_tests=_as_test_tuple(
                    entry.get('allow_tests'), field_name='allow_tests', item_id=item_id
                ),
                deny_tests=_as_test_tuple(
                    entry.get('deny_tests'), field_name='deny_tests', item_id=item_id
                ),
                note=note,
            )
        )
    return out


def load_h4_coverage_declarations(
    matrix_path: str | Path,
) -> tuple[list[H4CoverageDeclaration], list[H4CoverageDeclaration]]:
    """Load policy/role coverage declarations from the traceability YAML."""
    data = _load_yaml_mapping(Path(matrix_path))
    section = data.get(H4_COVERAGE_SECTION, {})
    if section is None:
        section = {}
    if not isinstance(section, dict):
        raise ValueError(f'{H4_COVERAGE_SECTION} must be a mapping')
    policies = _parse_declarations(
        section.get('policies'), kind='policy', id_key='policy_id'
    )
    roles = _parse_declarations(section.get('roles'), kind='role', id_key='role_id')
    return policies, roles


def inventory_h4_coverage_items(
    root: str | Path,
) -> tuple[list[H4CoverageItem], list[H4CoverageItem]]:
    """Inventory enabled policies and all RBAC roles for the workspace root."""
    root_path = Path(root).resolve()
    policies = [
        H4CoverageItem(
            kind='policy',
            item_id=policy.policy_id,
            name=policy.description or policy.policy_id,
            metadata={
                'policy_type': policy.policy_type.value,
                'effect': policy.effect.value,
                'precedence': policy.precedence.value,
            },
        )
        for policy in sorted(
            PolicyStore(root_path).list(enabled_only=True), key=lambda p: p.policy_id
        )
    ]
    roles = [
        H4CoverageItem(
            kind='role',
            item_id=role.role_id,
            name=role.name,
            metadata={
                'permissions': sorted(
                    permission.value for permission in role.permissions
                )
            },
        )
        for role in sorted(RoleStore(root_path).list_roles(), key=lambda r: r.role_id)
    ]
    return policies, roles


def _test_path_exists(root: Path, test_ref: str) -> bool:
    path_part = test_ref.split('::', 1)[0]
    path = Path(path_part)
    if not path.is_absolute():
        path = root / path
    return path.is_file()


def _coverage_gaps_for_kind(
    *,
    root: Path,
    kind: CoverageKind,
    items: list[H4CoverageItem],
    declarations: list[H4CoverageDeclaration],
) -> list[H4CoverageGap]:
    gaps: list[H4CoverageGap] = []
    declared = {decl.item_id: decl for decl in declarations}
    item_ids = {item.item_id for item in items}

    for item in items:
        decl = declared.get(item.item_id)
        if decl is None:
            gaps.append(
                H4CoverageGap(
                    kind=kind,
                    item_id=item.item_id,
                    issue='missing_declaration',
                    detail=f'{kind} is present in the workspace store but absent from {H4_COVERAGE_SECTION}',
                )
            )
            continue
        if not decl.allow_tests:
            gaps.append(
                H4CoverageGap(
                    kind=kind,
                    item_id=item.item_id,
                    issue='missing_allow_tests',
                    detail='declaration must list at least one allow-side test reference',
                )
            )
        if not decl.deny_tests:
            gaps.append(
                H4CoverageGap(
                    kind=kind,
                    item_id=item.item_id,
                    issue='missing_deny_tests',
                    detail='declaration must list at least one deny-side test reference',
                )
            )
        for ref in (*decl.allow_tests, *decl.deny_tests):
            if not _test_path_exists(root, ref):
                gaps.append(
                    H4CoverageGap(
                        kind=kind,
                        item_id=item.item_id,
                        issue='missing_test_file',
                        detail=f'test reference does not resolve to a file: {ref}',
                    )
                )

    for decl in declarations:
        if decl.item_id not in item_ids:
            gaps.append(
                H4CoverageGap(
                    kind=kind,
                    item_id=decl.item_id,
                    issue='stale_declaration',
                    detail=f'declaration exists but no matching {kind} is present in the workspace store',
                )
            )
    return gaps


def build_h4_coverage_report(
    root: str | Path,
    *,
    matrix_path: str | Path | None = None,
) -> H4CoverageReport:
    """Build the ADR-0031 criterion-2 coverage-completeness evidence report."""
    root_path = Path(root).resolve()
    matrix = (
        Path(matrix_path)
        if matrix_path is not None
        else root_path / 'docs' / 'architecture' / 'claim-to-test-traceability.yaml'
    )
    policy_declarations, role_declarations = load_h4_coverage_declarations(matrix)
    policies, roles = inventory_h4_coverage_items(root_path)
    gaps = [
        *_coverage_gaps_for_kind(
            root=root_path,
            kind='policy',
            items=policies,
            declarations=policy_declarations,
        ),
        *_coverage_gaps_for_kind(
            root=root_path,
            kind='role',
            items=roles,
            declarations=role_declarations,
        ),
    ]
    return H4CoverageReport(
        root=str(root_path),
        matrix_path=str(matrix),
        policies=policies,
        roles=roles,
        policy_declarations=policy_declarations,
        role_declarations=role_declarations,
        gaps=gaps,
    )
