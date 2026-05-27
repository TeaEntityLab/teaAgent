"""CLI handler for skill publish with cryptographic attestation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from teaagent.tsb_format import (
    TSBBuilder,
    TSBMetadata,
    TSBVerifier,
)


def print_json(value: dict) -> None:
    """Print value as JSON."""
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def skill_publish_command(args: argparse.Namespace) -> int:
    """Publish a skill with cryptographic attestation.
    
    Args:
        args: Command-line arguments.
        
    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        skill_path = Path(args.skill_path)
        audit_log_path = Path(args.audit_log)
        output_path = Path(args.output) if args.output else skill_path.parent / f"{skill_path.name}.tsb"
        author_key_path = Path(args.key) if args.key else None
        
        if not skill_path.exists():
            print_json({
                "status": "error",
                "message": f"Skill path not found: {skill_path}",
            })
            return 1
        
        if not audit_log_path.exists():
            print_json({
                "status": "error",
                "message": f"Audit log not found: {audit_log_path}",
            })
            return 1
        
        # Read skill metadata from SKILL.md or use defaults
        skill_name = args.name or skill_path.name
        skill_version = args.version or "1.0.0"
        skill_author = args.author or "unknown"
        
        metadata = TSBMetadata(
            skill_name=skill_name,
            skill_version=skill_version,
            skill_author=skill_author,
            created_at=datetime.utcnow().isoformat() + "Z",
            environment_type=args.environment_type,
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
        )
        
        print(f"[Packaging...] Building TSB for skill: {skill_name}")
        print(f"[Redacting...] Applying privacy filters to audit log...")
        
        builder = TSBBuilder(
            skill_path=skill_path,
            audit_log_path=audit_log_path,
            author_key_path=author_key_path,
        )
        
        manifest = builder.build_tsb(output_path, metadata)
        
        print(f"[✓] TSB created: {output_path}")
        print(f"[✓] Bundle hash: {manifest.attestation.bundle_hash}")
        print(f"[✓] Audit chain hash: {manifest.attestation.audit_chain_hash}")
        if manifest.attestation.author_signature:
            print(f"[✓] Author signature: {manifest.attestation.author_signature[:32]}...")
        
        print_json({
            "status": "success",
            "tsb_path": str(output_path),
            "skill_name": skill_name,
            "skill_version": skill_version,
            "bundle_hash": manifest.attestation.bundle_hash,
            "files_count": len(manifest.files),
        })
        return 0
        
    except Exception as exc:
        print_json({
            "status": "error",
            "message": str(exc),
        })
        return 1


def skill_verify_tsb_command(args: argparse.Namespace) -> int:
    """Verify a TSB file.
    
    Args:
        args: Command-line arguments.
        
    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        tsb_path = Path(args.tsb_path)
        
        if not tsb_path.exists():
            print_json({
                "status": "error",
                "message": f"TSB file not found: {tsb_path}",
            })
            return 1
        
        print(f"[Verifying...] Checking TSB integrity and attestation...")
        
        verifier = TSBVerifier(tsb_path)
        is_valid, message = verifier.verify(verify_signature=not args.skip_signature)
        
        if is_valid:
            print(f"[✓] {message}")
            print_json({
                "status": "success",
                "valid": True,
                "message": message,
            })
            return 0
        else:
            print(f"[✗] {message}")
            print_json({
                "status": "error",
                "valid": False,
                "message": message,
            })
            return 1
            
    except Exception as exc:
        print_json({
            "status": "error",
            "message": str(exc),
        })
        return 1
