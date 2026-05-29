"""Tests for P1/P2 remediation (security_env, concurrency hardening)."""

from __future__ import annotations

import hashlib
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from teaagent.audit import AuditLogger
from teaagent.audit_chain import verify_audit_chain
from teaagent.ergonomics.approval_store import ApprovalPresetStore
from teaagent.errors import ToolPermissionError
from teaagent.policy import ApprovalPolicy, PermissionMode, _verify_ssh_signature
from teaagent.tools import ToolRegistry
from teaagent.vote_relay import VoteRelayPayload, verify_relay_vote


class DevSignatureGateTests(unittest.TestCase):
    def test_dev_hash_rejected_by_default(self) -> None:
        pubkey = 'ssh-ed25519 AAAA'
        message = 'request-hash'
        expected = hashlib.sha256((message + pubkey).encode()).hexdigest()
        with mock.patch(
            'teaagent.security_env.allow_dev_signatures', return_value=False
        ):
            self.assertFalse(
                _verify_ssh_signature(
                    signature=expected,
                    message=message,
                    ssh_key_id='peer1',
                    peer_public_keys={'peer1': pubkey},
                    allow_dev_signatures=False,
                )
            )

    def test_dev_hash_allowed_when_explicit(self) -> None:
        pubkey = 'ssh-ed25519 AAAA'
        message = 'request-hash'
        expected = hashlib.sha256((message + pubkey).encode()).hexdigest()
        self.assertTrue(
            _verify_ssh_signature(
                signature=expected,
                message=message,
                ssh_key_id='peer1',
                peer_public_keys={'peer1': pubkey},
                allow_dev_signatures=True,
            )
        )


class PreapprovedCallIdTests(unittest.TestCase):
    def test_preapproved_call_id_creates_scoped_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            policy = ApprovalPolicy(
                approval_store=store,
                approval_origin_run_id='run-1',
                preapproved_call_ids=frozenset({'call-42'}),
            )
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-42',
                destructive=True,
                arguments={'path': 'x.txt', 'content': 'hi'},
            )
            self.assertIsNone(
                store.check_scoped_approval(
                    'run-1',
                    'call-42',
                    'workspace_write_file',
                    {'path': 'x.txt', 'content': 'hi'},
                )
            )


class ShellObfuscationTests(unittest.TestCase):
    def test_quote_stripping_rm_rf_prod(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg('rm -r"f" /prod')
        self.assertIn('rm', normalized)
        self.assertIn('/prod', normalized)

    def test_backtick_expansion(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg('echo `echo /prod`')
        self.assertIn('/prod', normalized)

    def test_brace_expansion(self) -> None:
        normalized = ApprovalPolicy._normalize_shell_arg('echo /pr{od,oduction}/app')
        self.assertIn('/prod/app', normalized)
        self.assertIn('/production/app', normalized)


class StrictLocalMcpTests(unittest.TestCase):
    def test_loopback_requires_auth_when_strict(self) -> None:
        from teaagent.mcp_http import build_mcp_http_server

        registry = ToolRegistry()
        with mock.patch(
            'teaagent.security_env.strict_local_services', return_value=True
        ):
            with self.assertRaises(ValueError) as ctx:
                build_mcp_http_server(registry, host='127.0.0.1', port=0)
            self.assertIn('TEAAGENT_STRICT_LOCAL', str(ctx.exception))


class AuditChainReloadTests(unittest.TestCase):
    def test_two_loggers_same_path_preserve_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'run.jsonl'
            a = AuditLogger(path=path)
            a.record('start', 'run-1', step=1)
            b = AuditLogger(path=path)
            b.record('finish', 'run-1', step=2)
            result = verify_audit_chain(path)
            self.assertTrue(result.valid, result.error)


class AtomicScopedApprovalTests(unittest.TestCase):
    def test_concurrent_consume_only_one_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            store.add_scoped_approval(
                run_id='run-1',
                call_id='call-1',
                tool_name='workspace_write_file',
                arguments={'path': 'foo.py'},
            )
            policy = ApprovalPolicy(
                permission_mode=PermissionMode.PROMPT,
                approval_store=store,
                approval_origin_run_id='run-1',
            )
            errors: list[Exception] = []

            def attempt() -> None:
                try:
                    policy.assert_allowed(
                        tool_name='workspace_write_file',
                        call_id='call-1',
                        destructive=True,
                        arguments={'path': 'foo.py'},
                    )
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=attempt) for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            success_count = sum(
                1 for exc in errors if isinstance(exc, ToolPermissionError)
            )
            self.assertEqual(success_count, 3)
            self.assertEqual(len(errors), 3)


class WorkflowRollbackTests(unittest.TestCase):
    def test_strict_validation_triggers_journal_restore(self) -> None:
        from teaagent.agent_factory import AgentFactory
        from teaagent.coordinator import (
            TaskClassification,
            TaskComplexity,
            TaskType,
            WorkflowPlan,
            WorkflowStep,
        )
        from teaagent.plugin_system import PluginRegistry
        from teaagent.run_undo import UndoResult
        from teaagent.workflow_engine import StepExecution, WorkflowEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            registry = PluginRegistry()
            factory = AgentFactory(registry, persist_to_disk=False)
            engine = WorkflowEngine(
                registry, factory, root=tmpdir, enable_self_healing=False
            )
            plan = WorkflowPlan(
                task_description='rollback test',
                classification=TaskClassification(
                    task_type=TaskType.GENERAL,
                    complexity=TaskComplexity.SIMPLE,
                    confidence=1.0,
                ),
                steps=[
                    WorkflowStep(
                        step_id=1,
                        description='step',
                        agent_name='agent',
                        tools=(),
                        validation_profile='strict',
                    )
                ],
            )
            audit = AuditLogger()
            failed = StepExecution(
                step_id=1,
                success=False,
                requires_rollback=True,
            )

            with (
                mock.patch.object(engine, '_execute_step', return_value=failed),
                mock.patch(
                    'teaagent.workflow_engine.UndoJournal.restore',
                    return_value=UndoResult(restored=[], deleted=[], errors=[]),
                ) as restore_mock,
            ):
                execution = engine.execute_workflow(plan, audit_logger=audit)
            self.assertTrue(restore_mock.called)
            from teaagent.workflow_engine import WorkflowState

            self.assertEqual(execution.state, WorkflowState.FAILED)


class RelayDevSignatureTests(unittest.TestCase):
    def test_dev_signature_rejected_without_allow_flag(self) -> None:
        from teaagent.consensus import (
            ConsensusConfig,
            ConsensusEngine,
            PeerIdentity,
            PeerRegistry,
            RiskLevel,
            VotingThreshold,
            peer_vote_signature,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            registry = PeerRegistry(storage_path=root / 'peers.json')
            peer = PeerIdentity(name='peer-a', ssh_public_key='ssh-ed25519 AAAA')
            registry.register(peer)
            registry.activate(peer.name)
            engine = ConsensusEngine(
                peer_registry=registry,
                config=ConsensusConfig(),
                storage_path=root / 'consensus.json',
            )
            state = engine.request_consensus(
                task_description='task',
                risk_level=RiskLevel.LOW,
                proposed_by='test',
                threshold=VotingThreshold.SIMPLE_MAJORITY,
            )
            sig = peer_vote_signature(
                peer,
                state.proposal.task_description,
                proposal_id=state.proposal.id,
                peer_name=peer.name,
                decision='approve',
            )
            payload = VoteRelayPayload(
                proposal_id=state.proposal.id,
                peer_name=peer.name,
                decision='approve',
                signature=sig,
            )
            ok, reason = verify_relay_vote(
                engine, payload, require_ssh=False, allow_dev_signatures=False
            )
            self.assertFalse(ok)
            self.assertIn('disabled', reason)


if __name__ == '__main__':
    unittest.main()
