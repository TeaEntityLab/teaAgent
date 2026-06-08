#!/usr/bin/env python3
"""Migrate legacy import paths to canonical ones project-wide (ARC-001/002)."""

import ast
from pathlib import Path

# Canonical symbols mapped to teaagent.types
TYPES_SYMBOLS = {
    'AgentHarnessError',
    'AuditDurabilityError',
    'BudgetExceededError',
    'ConfigError',
    'DenialReasonCode',
    'ErrorCategory',
    'InvalidToolDecision',
    'RunCancelledError',
    'ToolExecutionError',
    'ToolPermissionError',
    'ToolValidationError',
    'ToolAnnotations',
    'ToolDefinition',
    'ToolRateLimit',
    'ToolRegistry',
    'RunBudget',
    'FinalAnswer',
    'RunResult',
    'ToolRequest',
    'AuditEvent',
    'AuditLogger',
    'ChainVerificationResult',
    'compute_event_hash',
    'verify_audit_chain',
    'ApprovalRequest',
    'JITApprovalState',
    'PermissionMode',
}

# Canonical symbols mapped to teaagent.approval
APPROVAL_SYMBOLS = {
    'ApprovalManager',
    'ApprovalQueueStore',
    'CentralizedApprovalQueue',
    'ApprovalStoreManager',
    'DiffApprovalHandler',
    'JITApprovalManager',
    'JITApprovalServer',
    'MultiSigQuorumConfig',
    'MultiSigQuorumManager',
    'PeerSignature',
    'PermissionModeEnforcer',
    'format_denial_message',
    'parse_permission_mode',
    'ApprovalHandler',
}

LEGACY_MODULES = {
    'teaagent.errors',
    'teaagent.tools',
    'teaagent.budget',
    'teaagent.runner._types',
    'teaagent.audit',
    'teaagent.audit_chain',
    'teaagent.approval_manager',
    'teaagent.jit_approval_server',
    'teaagent.approval_ui',
    'teaagent.approval_backend',
    'teaagent.approval_selectors',
    'teaagent.policy',
    'teaagent.subagents._approval_queue',
    'teaagent.subagents._approval_queue_store',
}


EXCLUDED_PATHS = {
    'teaagent/errors.py',
    'teaagent/tools.py',
    'teaagent/budget.py',
    'teaagent/runner/_types.py',
    'teaagent/audit.py',
    'teaagent/audit_chain.py',
    'teaagent/approval_manager.py',
    'teaagent/jit_approval_server.py',
    'teaagent/approval_ui.py',
    'teaagent/approval_backend.py',
    'teaagent/approval_selectors.py',
    'teaagent/policy.py',
    'teaagent/subagents/_approval_queue.py',
    'teaagent/subagents/_approval_queue_store.py',
}


def migrate_file(path: Path) -> bool:
    # Only migrate tests, cli, tui, and examples
    path_str = str(path)
    allowed = False
    for pattern in ['/tests/', '/teaagent/cli/', '/teaagent/tui/', '/examples/']:
        if pattern in path_str:
            allowed = True
            break
    if not allowed:
        return False

    # Do not migrate types or approval packages themselves
    if 'teaagent/types' in str(path) or 'teaagent/approval' in str(path):
        return False

    try:
        content = path.read_text(encoding='utf-8')
        tree = ast.parse(content, filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return False

    imports_to_replace = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in LEGACY_MODULES:
            # Check if any imported symbol is canonicalized
            has_migrated_symbols = False
            for name_node in node.names:
                if (
                    name_node.name in TYPES_SYMBOLS
                    or name_node.name in APPROVAL_SYMBOLS
                ):
                    has_migrated_symbols = True
                    break

            if has_migrated_symbols:
                imports_to_replace.append(node)

    if not imports_to_replace:
        return False

    # Process imports in reverse order (from bottom to top) to keep line numbers valid
    imports_to_replace.sort(key=lambda n: n.lineno, reverse=True)
    lines = content.splitlines(keepends=True)

    modified = False
    for node in imports_to_replace:
        # Get the lines corresponding to this import statement
        start_idx = node.lineno - 1
        end_idx = getattr(node, 'end_lineno', node.lineno)

        # Separate symbols into categories
        types_list = []
        approval_list = []
        legacy_list = []

        for name_node in node.names:
            alias_str = f' as {name_node.asname}' if name_node.asname else ''
            full_name = f'{name_node.name}{alias_str}'
            if name_node.name in TYPES_SYMBOLS:
                types_list.append(full_name)
            elif name_node.name in APPROVAL_SYMBOLS:
                approval_list.append(full_name)
            else:
                legacy_list.append(full_name)

        new_imports = []
        if types_list:
            new_imports.append(
                f'from teaagent.types import {", ".join(sorted(types_list))}\n'
            )
        if approval_list:
            new_imports.append(
                f'from teaagent.approval import {", ".join(sorted(approval_list))}\n'
            )
        if legacy_list:
            new_imports.append(
                f'from {node.module} import {", ".join(sorted(legacy_list))}\n'
            )

        # Keep track of original indentation
        orig_line = lines[start_idx]
        indent = orig_line[: len(orig_line) - len(orig_line.lstrip())]
        indented_imports = [indent + imp if imp.strip() else imp for imp in new_imports]

        # Replace lines in place
        lines[start_idx:end_idx] = indented_imports
        modified = True

    if modified:
        new_content = ''.join(lines)
        path.write_text(new_content, encoding='utf-8')
        return True

    return False


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    count = 0
    for path in sorted(root.rglob('*.py')):
        if migrate_file(path):
            print(f'Migrated: {path.relative_to(root)}')
            count += 1
    print(f'Total files migrated: {count}')


if __name__ == '__main__':
    main()
