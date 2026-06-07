from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path
from typing import Any

from teaagent.audit import AuditLogger
from teaagent.audit_chain import verify_audit_chain
from teaagent.audit_export import export_compliance_bundle, write_compliance_bundle
from teaagent.cli._output import print_json
from teaagent.cli.execution import AgentExecutionFactory
from teaagent.ssh_signatures import sign_message_ssh


def audit_list_command(args: argparse.Namespace) -> int:
    store = AgentExecutionFactory(args.root).create_run_store(readonly=True)
    print_json([summary.to_dict() for summary in store.list_runs(limit=args.limit)])
    return 0


def audit_show_command(args: argparse.Namespace) -> int:
    store = AgentExecutionFactory(args.root).create_run_store(readonly=True)
    try:
        events = store.show_run(args.run_id)
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1

    with_reasoning = getattr(args, 'with_reasoning', False)
    if with_reasoning:
        reasoning_entries: list[dict[str, Any]] = []
        for evt in events:
            payload = evt.get('payload', {})
            reasoning = payload.get('reasoning')
            if reasoning is not None:
                reasoning_entries.append(
                    {
                        'event_type': evt.get('event_type'),
                        'tool_name': payload.get('tool_name'),
                        'call_id': payload.get('call_id'),
                        'reasoning': reasoning,
                    }
                )
        print_json(
            {
                'run_id': args.run_id,
                'events': events,
                'reasoning_entries': reasoning_entries,
            }
        )
    else:
        print_json(events)
    return 0


def audit_tail_command(args: argparse.Namespace) -> int:
    store = AgentExecutionFactory(args.root).create_run_store(readonly=True)
    try:
        events = store.show_run(args.run_id)
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1

    from teaagent.audit_tail import format_audit_tail_human, tail_audit_events

    limit = int(getattr(args, 'limit', 20) or 20)
    if getattr(args, 'human', False):
        print(format_audit_tail_human(events, limit=limit))
        return 0
    print_json(
        {
            'run_id': args.run_id,
            'limit': limit,
            'events': tail_audit_events(events, limit=limit),
        }
    )
    return 0


def audit_prune_command(args: argparse.Namespace) -> int:
    if args.days is None and args.keep is None and not args.all:
        print_json(
            {
                'status': 'error',
                'message': 'audit prune requires --days, --keep, or --all',
            }
        )
        return 1
    store = AgentExecutionFactory(args.root).create_run_store()
    cutoff = time.time() - (args.days * 86400) if args.days is not None else None
    run_paths = sorted(
        store.store_dir.glob('*.jsonl'), key=lambda p: p.stat().st_mtime, reverse=True
    )
    keep = set(run_paths[: args.keep]) if args.keep is not None else set()
    deleted: list[str] = []
    for path in run_paths:
        if path in keep:
            continue
        if cutoff is not None and path.stat().st_mtime >= cutoff:
            continue
        path.unlink(missing_ok=True)
        path.with_suffix(path.suffix + '.lock').unlink(missing_ok=True)
        deleted.append(path.name)
    print_json({'count': len(deleted), 'deleted': deleted})
    return 0


def audit_serve_command(args: argparse.Namespace) -> int:
    from teaagent.audit_viewer import serve_audit_viewer

    store = AgentExecutionFactory(args.root).create_run_store(readonly=True)
    serve_audit_viewer(store, host=args.host, port=args.port)
    return 0


def audit_verify_command(args: argparse.Namespace) -> int:
    """Verify cryptographic audit chain integrity and optionally sign attestation."""
    audit_log_path = Path(args.root) / '.teaagent' / 'audit.jsonl'

    if not audit_log_path.exists():
        print_json(
            {'status': 'error', 'message': f'Audit log not found at {audit_log_path}'}
        )
        return 1

    print('[Verifying...] Scanning audit events against genesis block...')
    result = verify_audit_chain(audit_log_path)

    if not result.valid:
        print_json(
            {
                'status': 'invalid',
                'event_count': result.event_count,
                'error': result.error,
            }
        )
        return 1

    print(
        '[✓] Cryptographic Hash Chain: VALID (zero gaps, zero modifications, zero insertions).'
    )
    print(f'[✓] Verified {result.event_count} audit events.')

    # Handle signature generation if requested
    if args.signature:
        signature_path = audit_log_path.with_suffix('.jsonl.sig')
        key_path = Path(args.signature).expanduser()

        if not key_path.exists():
            print_json(
                {'status': 'error', 'message': f'Signature key not found at {key_path}'}
            )
            return 1

        # Reject public keys for signing
        if key_path.suffix == '.pub':
            print_json(
                {
                    'status': 'error',
                    'message': f'Cannot sign with public key: {key_path}. Provide a private key.',
                }
            )
            return 1

        print(f'[Attesting...] Generating provenance signature using {key_path}...')

        try:
            # Read the audit log content
            audit_content = audit_log_path.read_text(encoding='utf-8')

            # Generate signature using SSH key or GPG
            if key_path.suffix == '' or 'ssh' in key_path.name.lower():
                # SSH key signing - use the existing helper
                signature_content = sign_message_ssh(
                    key_path, audit_content, namespace='teaagent-audit'
                )
                signature_path.write_text(signature_content, encoding='utf-8')
            else:
                # GPG key signing
                proc = subprocess.run(
                    [
                        'gpg',
                        '--default-key',
                        str(key_path),
                        '--detach-sign',
                        '--armor',
                        '--output',
                        str(signature_path),
                        str(audit_log_path),
                    ],
                    capture_output=True,
                )

                if proc.returncode != 0:
                    print_json(
                        {
                            'status': 'error',
                            'message': f'GPG signature failed: {proc.stderr.decode()}',
                        }
                    )
                    return 1

            print(f'[✓] Attestation Signature written to: {signature_path}')

        except FileNotFoundError as e:
            print_json(
                {
                    'status': 'error',
                    'message': f'Signing tool not found: {e}. Ensure ssh-keygen or gpg is installed.',
                }
            )
            return 1
        except Exception as e:
            print_json(
                {'status': 'error', 'message': f'Signature generation failed: {e}'}
            )
            return 1

    print_json(
        {
            'status': 'valid',
            'event_count': result.event_count,
            'signature_file': str(audit_log_path.with_suffix('.jsonl.sig'))
            if args.signature
            else None,
        }
    )
    return 0


def audit_export_command(args: argparse.Namespace) -> int:
    store = AgentExecutionFactory(args.root).create_run_store(readonly=True)
    try:
        events = store.show_run(args.run_id)
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1

    log_path = store.run_path(args.run_id)
    bundle = export_compliance_bundle(
        events,
        run_id=args.run_id,
        include_chain_verification=not args.skip_chain_verify,
        log_path=log_path if not args.skip_chain_verify else None,
    )

    output_path = getattr(args, 'output', None)
    if output_path:
        written = write_compliance_bundle(
            bundle, Path(output_path), pretty=not args.compact
        )
        print_json({'status': 'ok', 'output': str(written), 'event_count': len(events)})
    else:
        print_json(bundle)
    return 0


def audit_decrypt_command(args: argparse.Namespace) -> int:
    """Decrypt an L3 audit log file."""
    audit_path = Path(args.audit_path)

    if not audit_path.exists():
        print_json(
            {'status': 'error', 'message': f'Audit log not found at {audit_path}'}
        )
        return 1

    # Load encryption key if provided
    encryption_key = None
    if args.key:
        key_path = Path(args.key).expanduser()
        if not key_path.exists():
            print_json(
                {
                    'status': 'error',
                    'message': f'Encryption key not found at {key_path}',
                }
            )
            return 1
        try:
            encryption_key = key_path.read_bytes()
        except OSError as exc:
            print_json(
                {'status': 'error', 'message': f'Failed to read encryption key: {exc}'}
            )
            return 1

    try:
        result = AuditLogger.decrypt_audit_log(audit_path, encryption_key)
        print_json(
            {
                'status': 'ok',
                'event_count': result['total_events'],
                'chain_valid': result['chain_valid'],
                'chain_errors': result['chain_errors'],
                'events': result['events'],
            }
        )
        return 0
    except ValueError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    except Exception as exc:
        print_json({'status': 'error', 'message': f'Decryption failed: {exc}'})
        return 1
