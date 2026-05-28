"""TSB Supply Chain Security Auditor - Reference Implementation.

This skill demonstrates TeaAgent's TSB verification capabilities
for supply chain security auditing.
"""

import sys
from pathlib import Path
from typing import Any, Dict, Optional


def verify_tsb_bundle(
    tsb_path: Path,
    identity: Optional[str] = None,
    issuer: Optional[str] = None,
    offline: bool = False,
) -> Dict[str, Any]:
    """Verify a TSB bundle's security and provenance.

    Args:
        tsb_path: Path to the .tsb file.
        identity: Optional OIDC identity to enforce (e.g., email).
        issuer: Optional OIDC issuer to enforce.
        offline: If True, skip Rekor/Fulcio online verification.

    Returns:
        Dictionary containing verification results.
    """
    from teaagent.tsb_format import TSBVerifier

    print(f'[TSB Auditor] Verifying bundle: {tsb_path}')

    if not tsb_path.exists():
        return {
            'success': False,
            'error': f'TSB file not found: {tsb_path}',
        }

    # Configure verification
    verifier = TSBVerifier(tsb_path, offline=offline)

    print(f'[TSB Auditor] Verification mode: {"offline" if offline else "online"}')
    if identity:
        print(f'[TSB Auditor] Enforcing identity: {identity}')
    if issuer:
        print(f'[TSB Auditor] Enforcing issuer: {issuer}')

    # Perform verification
    is_valid, message = verifier.verify(
        verify_signature=True,
        identity=identity,
        issuer=issuer,
    )

    result = {
        'success': is_valid,
        'message': message,
        'offline_mode': offline,
        'identity_policy': identity,
        'issuer_policy': issuer,
    }

    if is_valid:
        print(f'[TSB Auditor] ✓ Verification successful: {message}')
    else:
        print(f'[TSB Auditor] ✗ Verification failed: {message}')

    return result


def extract_tsb_bundle(tsb_path: Path, output_path: Path) -> Dict[str, Any]:
    """Extract a verified TSB bundle to a directory.

    Args:
        tsb_path: Path to the .tsb file.
        output_path: Directory to extract the skill to.

    Returns:
        Dictionary containing extraction results.
    """
    from teaagent.tsb_format import TSBVerifier

    print(f'[TSB Auditor] Extracting bundle to: {output_path}')

    verifier = TSBVerifier(tsb_path)

    try:
        verifier.extract_skill(output_path)

        # Verify extraction
        if output_path.exists():
            files = list(output_path.rglob('*'))
            print(f'[TSB Auditor] Extracted {len(files)} files')

            return {
                'success': True,
                'output_path': str(output_path),
                'files_extracted': len(files),
            }
        else:
            return {
                'success': False,
                'error': 'Extraction completed but output directory not found',
            }
    except Exception as exc:
        return {
            'success': False,
            'error': f'Extraction failed: {exc}',
        }


def audit_tsb_provenance(
    tsb_path: Path,
    require_identity: Optional[str] = None,
    require_issuer: Optional[str] = None,
    offline: bool = False,
    extract_to: Optional[Path] = None,
) -> Dict[str, Any]:
    """Complete TSB provenance audit workflow.

    Args:
        tsb_path: Path to the .tsb file.
        require_identity: Optional OIDC identity to enforce.
        require_issuer: Optional OIDC issuer to enforce.
        offline: If True, skip online verification.
        extract_to: Optional path to extract the skill after verification.

    Returns:
        Dictionary containing complete audit results.
    """
    print('[TSB Auditor] Starting provenance audit...')
    print('=' * 60)

    # Step 1: Verify the bundle
    verification = verify_tsb_bundle(
        tsb_path,
        identity=require_identity,
        issuer=require_issuer,
        offline=offline,
    )

    if not verification['success']:
        print('[TSB Auditor] Audit failed: verification unsuccessful')
        return verification

    # Step 2: Extract if requested
    if extract_to:
        extraction = extract_tsb_bundle(tsb_path, extract_to)
        verification['extraction'] = extraction

        if not extraction['success']:
            print('[TSB Auditor] Warning: extraction failed')

    print('=' * 60)
    print('[TSB Auditor] Audit complete')

    return verification


def print_audit_report(result: Dict[str, Any]) -> None:
    """Print a formatted audit report.

    Args:
        result: Verification result dictionary.
    """
    print('\n' + '=' * 60)
    print('TSB SECURITY AUDIT REPORT')
    print('=' * 60)

    print(f'Status: {"✓ PASSED" if result["success"] else "✗ FAILED"}')
    print(f'Message: {result["message"]}')
    print(f'Mode: {"Offline" if result.get("offline_mode") else "Online"}')

    if result.get('identity_policy'):
        print(f'Identity Policy: {result["identity_policy"]}')
    if result.get('issuer_policy'):
        print(f'Issuer Policy: {result["issuer_policy"]}')

    if 'extraction' in result:
        ext = result['extraction']
        print(f'\nExtraction: {"✓ Success" if ext["success"] else "✗ Failed"}')
        if ext['success']:
            print(f'Output: {ext["output_path"]}')
            print(f'Files: {ext["files_extracted"]}')

    print('=' * 60)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python main.py <tsb_path> [options]')
        print('Options:')
        print('  --identity <email>    Require specific OIDC identity')
        print('  --issuer <url>        Require specific OIDC issuer')
        print('  --offline             Skip online verification')
        print('  --extract <path>      Extract skill after verification')
        sys.exit(1)

    tsb_path = Path(sys.argv[1])
    identity = None
    issuer = None
    offline = False
    extract_to = None

    # Parse options
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--identity' and i + 1 < len(sys.argv):
            identity = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--issuer' and i + 1 < len(sys.argv):
            issuer = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--offline':
            offline = True
            i += 1
        elif sys.argv[i] == '--extract' and i + 1 < len(sys.argv):
            extract_to = Path(sys.argv[i + 1])
            i += 2
        else:
            i += 1

    result = audit_tsb_provenance(
        tsb_path,
        require_identity=identity,
        require_issuer=issuer,
        offline=offline,
        extract_to=extract_to,
    )

    print_audit_report(result)

    sys.exit(0 if result['success'] else 1)
