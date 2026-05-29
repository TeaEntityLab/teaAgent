"""WASM skill contract helpers for native skill modules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from teaagent.skill_executor import _find_wasm_file
from teaagent.wasm_runtime import WASMRuntime, is_wasm_available

WASM_MANIFEST_NAME = 'wasm_manifest.json'


def build_wasm_invoke_contract(skill_path: Path) -> dict[str, Any]:
    """Describe expected WASM exports and payload schema for a skill directory."""
    skill_path = skill_path.resolve()
    wasm_file = _find_wasm_file(skill_path)
    return {
        'skill_path': str(skill_path),
        'wasm_file': str(wasm_file) if wasm_file else None,
        'runtime_available': is_wasm_available(),
        'exports': ['run'],
        'payload_schema': {
            'type': 'object',
            'description': 'JSON object passed to WASM run export',
        },
        'memory_limit_mb': 256,
    }


def write_wasm_manifest(skill_path: Path, *, memory_limit_mb: int = 256) -> Path:
    """Write ``wasm_manifest.json`` beside the skill for external toolchain builds."""
    skill_path = skill_path.resolve()
    contract = build_wasm_invoke_contract(skill_path)
    contract['memory_limit_mb'] = memory_limit_mb
    manifest_path = skill_path / WASM_MANIFEST_NAME
    manifest_path.write_text(json.dumps(contract, indent=2), encoding='utf-8')
    return manifest_path


def validate_wasm_skill(
    skill_path: Path, *, memory_limit_mb: int = 256
) -> dict[str, Any]:
    """Validate WASM module presence and runtime compatibility."""
    skill_path = skill_path.resolve()
    wasm_file = _find_wasm_file(skill_path)
    if wasm_file is None:
        return {
            'compatible': False,
            'reason': 'No .wasm module found (tool.wasm, skill.wasm, or *.wasm)',
            'wasm_file': None,
        }
    if not is_wasm_available():
        return {
            'compatible': False,
            'reason': 'WASM runtime (wasmer) is not installed',
            'wasm_file': str(wasm_file),
        }
    runtime = WASMRuntime(memory_limit_mb=memory_limit_mb)
    check = runtime.check_compatibility(skill_path)
    compatible = bool(check.get('compatible'))
    issues = check.get('issues') or []
    return {
        'compatible': compatible,
        'reason': '' if compatible else '; '.join(str(item) for item in issues),
        'wasm_file': str(wasm_file),
    }
