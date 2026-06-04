"""SSH signature helpers for production consensus votes (OpenSSH ``ssh-keygen -Y``)."""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

VOTE_SIGNATURE_NAMESPACE = 'teaagent-consensus-vote'


def build_vote_signing_message(
    proposal_id: str,
    peer_name: str,
    decision: str,
    task_description: str,
) -> str:
    """Canonical vote payload signed by peers and verified by the relay."""
    return '\n'.join(
        (
            proposal_id,
            peer_name,
            decision,
            task_description,
        )
    )


def is_ssh_signature_blob(signature: str) -> bool:
    """Return True when *signature* looks like an OpenSSH signature block."""
    return '-----BEGIN' in signature and 'SIGNATURE' in signature.upper()


def sign_message_ssh(
    private_key_path: Path,
    message: str,
    *,
    namespace: str = VOTE_SIGNATURE_NAMESPACE,
) -> str:
    """Sign *message* with ``ssh-keygen -Y sign``."""
    key_path = private_key_path.expanduser().resolve()
    if not key_path.is_file():
        raise FileNotFoundError(f'SSH private key not found: {key_path}')
    with tempfile.NamedTemporaryFile(
        mode='w', encoding='utf-8', suffix='.txt', delete=False
    ) as msg_file:
        msg_file.write(message)
        msg_path = Path(msg_file.name)
    try:
        proc = subprocess.run(
            [
                'ssh-keygen',
                '-Y',
                'sign',
                '-f',
                str(key_path),
                '-n',
                namespace,
                str(msg_path),
            ],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                proc.stderr.decode('utf-8', errors='replace') or 'sign failed'
            )
        sig_path = Path(str(msg_path) + '.sig')
        if sig_path.is_file():
            return sig_path.read_text(encoding='utf-8')
        return proc.stdout.decode('utf-8')
    finally:
        msg_path.unlink(missing_ok=True)
        Path(str(msg_path) + '.sig').unlink(missing_ok=True)


def verify_message_ssh(
    public_key_material: str,
    message: str,
    signature: str,
    *,
    namespace: str = VOTE_SIGNATURE_NAMESPACE,
) -> bool:
    """Verify *signature* over *message* using ``ssh-keygen -Y verify``."""
    pubkey = public_key_material.strip()
    if not pubkey or not signature.strip():
        return False
    try:
        with tempfile.TemporaryDirectory(prefix='teaagent-ssh-verify-') as tmp:
            base = Path(tmp)
            allowed = base / 'allowed_signers'
            sig_path = base / 'signature'
            msg_path = base / 'message.txt'
            parts = pubkey.split()
            if len(parts) < 2:
                return False
            key_type, key_data = parts[0], parts[1]
            principal = 'teaagent-peer'
            allowed.write_text(
                f'{principal} namespaces="{namespace}" {key_type} {key_data}\n',
                encoding='utf-8',
            )
            sig_path.write_text(signature, encoding='utf-8')
            msg_path.write_text(message, encoding='utf-8')
            proc = subprocess.run(
                [
                    'ssh-keygen',
                    '-Y',
                    'verify',
                    '-f',
                    str(allowed),
                    '-I',
                    principal,
                    '-n',
                    namespace,
                    '-s',
                    str(sig_path),
                ],
                input=message.encode('utf-8'),
                capture_output=True,
                check=False,
                timeout=15,
            )
            return proc.returncode == 0
    except subprocess.TimeoutExpired:
        logger.warning('SSH signature verify timed out')
        return False
    except OSError as exc:
        logger.debug('SSH verify failed: %s', exc)
        return False
