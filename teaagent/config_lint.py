"""Runtime configuration lint for unsafe combinations (WS4-005)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from teaagent.approval.manager import MultiSigQuorumConfig, PermissionMode
from teaagent.security_env import allow_dev_signatures

_DEV_WORKSPACE_ENV_VALUES = frozenset({'1', 'true', 'yes', 'on'})


@dataclass(frozen=True)
class ConfigLintFinding:
    severity: str
    code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {'severity': self.severity, 'code': self.code, 'message': self.message}


def _is_development_workspace(root_path: Path) -> bool:
    """True when the workspace is explicitly marked for local development."""
    env_flag = os.environ.get('TEAAGENT_DEVELOPMENT_WORKSPACE', '').strip().lower()
    if env_flag in _DEV_WORKSPACE_ENV_VALUES:
        return True
    return (root_path / '.teaagent' / 'development').is_file()


def _dev_signature_sources(root_path: Path) -> tuple[bool, bool]:
    """Return (env_enabled, config_enabled) for dev-hash signature acceptance."""
    multi_sig = MultiSigQuorumConfig.from_workspace_config(root_path)
    return allow_dev_signatures(), multi_sig.allow_dev_signatures


def lint_runtime_config(
    *,
    root: str | Path = '.',
    permission_mode: str | PermissionMode = PermissionMode.PROMPT,
    allow_destructive: bool = False,
    subagent_isolation: str | None = None,
) -> list[ConfigLintFinding]:
    findings: list[ConfigLintFinding] = []
    root_path = Path(root).resolve()
    audit_dir = root_path / '.teaagent' / 'runs'
    if not audit_dir.exists():
        findings.append(
            ConfigLintFinding(
                severity='warning',
                code='missing_audit_path',
                message=(
                    'No .teaagent/runs audit directory yet; durable run evidence '
                    'may be unavailable until the first agent run.'
                ),
            )
        )

    mode = (
        permission_mode
        if isinstance(permission_mode, PermissionMode)
        else PermissionMode(str(permission_mode))
    )
    if mode == PermissionMode.ALLOW and allow_destructive:
        findings.append(
            ConfigLintFinding(
                severity='error',
                code='permissive_destructive',
                message=(
                    'permission-mode=allow with destructive tools enabled bypasses '
                    'human approval entirely.'
                ),
            )
        )
    elif mode == PermissionMode.ALLOW:
        findings.append(
            ConfigLintFinding(
                severity='warning',
                code='permissive_allow_mode',
                message='permission-mode=allow skips approval prompts for destructive tools.',
            )
        )

    isolation = (
        (subagent_isolation or os.environ.get('TEAAGENT_SUBAGENT_ISOLATION') or '')
        .strip()
        .lower()
    )
    if isolation == 'shared':
        findings.append(
            ConfigLintFinding(
                severity='warning',
                code='shared_subagent_isolation',
                message=(
                    'Subagent isolation is shared; child writes apply directly to the '
                    'parent workspace. Prefer worktree default on git repos.'
                ),
            )
        )

    if not os.environ.get('TEAAGENT_MAX_ESTIMATED_COST_CENTS') and not os.environ.get(
        'TEAAGENT_BUDGET_CAP_CENTS'
    ):
        findings.append(
            ConfigLintFinding(
                severity='info',
                code='unclear_cost_policy',
                message=(
                    'No explicit cost cap env var set (TEAAGENT_MAX_ESTIMATED_COST_CENTS). '
                    'Runs use CLI/default budget limits only.'
                ),
            )
        )

    env_dev_sigs, config_dev_sigs = _dev_signature_sources(root_path)
    if (env_dev_sigs or config_dev_sigs) and not _is_development_workspace(root_path):
        sources: list[str] = []
        if env_dev_sigs:
            sources.append('TEAAGENT_ALLOW_DEV_SIGNATURES')
        if config_dev_sigs:
            sources.append('multi_sig.allow_dev_signatures in .teaagent/config.json')
        source_text = ' and '.join(sources)
        findings.append(
            ConfigLintFinding(
                severity='warning',
                code='dev_signatures_enabled',
                message=(
                    f'{source_text} enables dev-hash signatures that bypass '
                    'cryptographic verification. Mark a development workspace with '
                    'TEAAGENT_DEVELOPMENT_WORKSPACE=1 or .teaagent/development before '
                    'using this outside local harness work; never enable in production.'
                ),
            )
        )

    compliance_raw = os.environ.get('TEAAGENT_COMPLIANCE_MODE')
    if (
        compliance_raw is not None
        and compliance_raw.strip().lower() in {'0', 'false', 'no', 'off'}
        and mode == PermissionMode.ALLOW
    ):
        findings.append(
            ConfigLintFinding(
                severity='warning',
                code='compliance_mode_off',
                message=(
                    'TEAAGENT_COMPLIANCE_MODE is off while using permissive tool settings; '
                    'audit disk failures will not stop runs.'
                ),
            )
        )

    return findings
