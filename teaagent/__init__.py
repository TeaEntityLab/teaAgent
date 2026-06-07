"""Governance-first agent harness."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING

try:
    __version__ = version('teaagent')
except PackageNotFoundError:
    __version__ = '0+local'

from teaagent._lazy_exports import _EXPORTS, lazy_dir, lazy_getattr


def __getattr__(name: str) -> object:
    return lazy_getattr(name)


def __dir__() -> list[str]:
    return lazy_dir()


__all__ = [
    '__version__',
    *sorted(_EXPORTS),
]


if TYPE_CHECKING:
    from importlib.metadata import PackageNotFoundError

    from teaagent.a2a_trace import (
        TraceparentError,
        generate_traceparent,
        parse_traceparent,
    )
    from teaagent.agentcard import AgentCard, CircuitBreakerConfig
    from teaagent.aibom import AIBOMComponent, AIBOMManifest, build_aibom
    from teaagent.anp_adapter import (
        ANPAdapterError,
        ANPBidirectionalRouter,
        ANPDelegationResult,
        ANPGovernedInboundResult,
        ANPGovernedService,
        ANPInboundAdapter,
        ANPOutboundClient,
        ANPRoutingResult,
    )
    from teaagent.approval_ui import DiffApprovalHandler
    from teaagent.audit import AuditEvent, AuditLogger
    from teaagent.audit_chain import (
        ChainVerificationResult,
        compute_event_hash,
        verify_audit_chain,
    )
    from teaagent.auto_mode import AutoModeConfig, AutoModeGuard, AutoModeLimitError
    from teaagent.benchmark import (
        BenchmarkBaseline,
        BenchmarkResult,
        BenchmarkSuite,
        CaseMetrics,
        run_benchmark,
    )
    from teaagent.browser_tools import HAS_PLAYWRIGHT, register_browser_tools
    from teaagent.budget import RunBudget
    from teaagent.chat_agent import (
        ChatAgentConfig,
        ModelDecisionEngine,
        register_subagent_tool,
        run_chat_agent,
    )
    from teaagent.code_analysis import (
        CodeAnalysisConfig,
        CodeReference,
        CodeRelation,
        LSPServerConfig,
    )
    from teaagent.code_mode import (
        CodeModeResult,
        CodeModeSandbox,
        ContainerCodeModeBackend,
        UnsafeCodeError,
        execute_code_mode,
    )
    from teaagent.config_loader import (
        CONFIG_KEYS,
        ConfigLayer,
        ConfigResolver,
        ResolvedConfig,
        load_workspace_config,
    )
    from teaagent.context import ContextCompactor
    from teaagent.daily import (
        DailyBrief,
        DailyRecommendation,
        HarnessHealthReport,
        RunRollup,
        TokenBudgetReport,
        build_daily_brief,
    )
    from teaagent.errors import RunCancelledError
    from teaagent.eval import EvalCase, EvalReport, run_eval
    from teaagent.eval_report import render_html_report
    from teaagent.external_backends import (
        BackendAdapter,
        BackendAdapterFactory,
        BackendAdapterRegistry,
        BackendConfig,
        BackendError,
        BackendExecutionError,
        CodegraphMcpAdapter,
        CodeParseBackend,
        CxCliAdapter,
        KnowledgeSearchBackend,
        LocalKnowledgeAdapter,
        QmdCliAdapter,
        QmdMcpAdapter,
        get_code_parse_backend,
        get_default_registry,
        get_knowledge_backend,
    )
    from teaagent.file_policy import DenyRule, FilePolicy, load_file_policy
    from teaagent.graph_rag import GraphEdge, KnowledgeGraph, graph_retrieve
    from teaagent.graphqlite_store import (
        GraphQLiteConfig,
        GraphQLiteGraphStore,
        GraphQLiteRuntimeError,
    )
    from teaagent.heartbeat import Heartbeat
    from teaagent.hooks import (
        HookConfig,
        HookError,
        HookRegistry,
        format_check_hook,
        lint_check_hook,
        post_lint_check_hook,
        run_tests_hook,
        shell_command_hook,
    )
    from teaagent.hybrid_search import (
        HybridSearchBackend,
        get_hybrid_backend,
        register_hybrid_backend,
    )
    from teaagent.intent import (
        ClarificationResult,
        IntentScore,
        build_task_spec,
        clarify_task,
    )
    from teaagent.llm import (
        LLMConfigurationError,
        LLMHTTPError,
        LLMMessage,
        LLMProviderError,
        LLMRequest,
        LLMResponse,
        LLMResponseFormatError,
        ProviderConfig,
        available_providers,
        check_llm_configuration,
        create_llm_adapter,
    )
    from teaagent.llm_conformance import (
        ModelConformanceReport,
        ModelConformanceResult,
        run_model_conformance,
    )
    from teaagent.managed_runtime import managed_runtime_context
    from teaagent.mcp_client import MCPClientError, MCPHTTPClient
    from teaagent.mcp_http import build_mcp_http_server, serve_mcp_http
    from teaagent.mcp_server import handle_mcp_request, serve_mcp_stdio
    from teaagent.mcp_tool_adapter import register_mcp_tools
    from teaagent.memory import MemoryCatalog, MemoryEntry
    from teaagent.model_routing import ModelRoute, classify_task, route_model
    from teaagent.notify import NotifyConfig, fire_notification
    from teaagent.oauth21 import (
        HAS_CRYPTOGRAPHY,
        DPoPValidationResult,
        InMemoryOAuthStore,
        InvalidClientError,
        InvalidDPoPError,
        InvalidGrantError,
        JWTError,
        OAuth21AuthorizationServer,
        OAuth21Client,
        OAuth21ResourceServer,
        OAuth21TokenClaims,
        OAuth21TokenResponse,
        OAuthKeyRing,
        OAuthStore,
        SQLiteOAuthStore,
        compute_jwk_thumbprint,
        compute_s256_challenge,
        create_jwt,
        decode_jwt_unsafe,
        generate_code_verifier,
        verify_jwt,
    )
    from teaagent.plugins import PluginLoadResult, load_plugins
    from teaagent.policy import ApprovalPolicy, PermissionMode, parse_permission_mode
    from teaagent.portability import PortabilityResult, ProviderProfile
    from teaagent.preflight import PreflightReport, preflight
    from teaagent.prompt import (
        PromptBundle,
        assemble_agent_prompt,
        parse_model_decision,
    )
    from teaagent.rag import Document, InMemoryRetriever, agentic_retrieve
    from teaagent.readiness import ReadinessReport
    from teaagent.redaction import RedactionConfig
    from teaagent.run_export import ExportManifest, export_run, import_run
    from teaagent.run_store import RunStore, RunSummary
    from teaagent.run_undo import UndoJournal, UndoResult
    from teaagent.runner import (
        AgentRunner,
        ApprovalRequest,
        Decision,
        FinalAnswer,
        ToolRequest,
    )
    from teaagent.skill_loader import (
        SkillContent,
        SkillLoadReport,
        SkillLoadSkipped,
        SkillLoadWarning,
        load_skills,
        load_skills_with_report,
        skills_to_prompt_section,
    )
    from teaagent.skill_review import SkillReviewResult, review_skill
    from teaagent.stateless_mcp import StatelessMCPRequest, StatelessMCPResponse
    from teaagent.subagents import SubagentDef, SubagentManager, SubagentSession
    from teaagent.telemetry import (
        HAS_OTEL,
        InMemoryMetricsSink,
        MetricSnapshot,
        OTelAuditSink,
        OTelMetricsSink,
        TelemetryConfig,
        TelemetryNotAvailable,
        TracingHTTPTransport,
        configure_metrics,
        configure_telemetry,
    )
    from teaagent.tools import ToolAnnotations, ToolRateLimit, ToolRegistry
    from teaagent.trace import TraceRecorder
    from teaagent.ultrawork import UltraworkStore, WorkerRecord
    from teaagent.webhook_sink import WebhookAuditSink
    from teaagent.workspace_tools import (
        GitToolConfig,
        ToolRegistryBuilder,
        WorkspaceToolConfig,
        register_git_tools,
    )
