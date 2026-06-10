"""WDA-005 update platform proof."""

from __future__ import annotations

from tempfile import TemporaryDirectory

from teaagent.governance.update_platform import run_update_platform_proof


def test_update_platform_proof_install_and_rollback() -> None:
    with TemporaryDirectory() as tmp:
        proof = run_update_platform_proof(work_dir=tmp, platform='test')
        assert proof.from_version == '1.0.0'
        assert proof.to_version == '2.0.0'
        assert proof.rollback_ok is True
        assert len(proof.artifact_sha256) == 64
