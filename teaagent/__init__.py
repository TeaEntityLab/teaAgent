"""Governance-first agent harness."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version('teaagent')
except PackageNotFoundError:
    __version__ = '0+local'

from teaagent.aibom import AIBOMManifest, build_aibom
from teaagent.audit import AuditLogger
from teaagent.budget import RunBudget
from teaagent.chat_agent import (
    ChatAgentConfig,
    ModelDecisionEngine,
    register_subagent_tool,
    run_chat_agent,
)
from teaagent.code_mode import (
    ChildProcessCodeModeBackend,
    CodeModeResult,
    CodeModeSandbox,
    ContainerCodeModeBackend,
    UnsafeCodeError,
    execute_code_mode,
)
from teaagent.context import ContextCompactor
from teaagent.errors import RunCancelledError
from teaagent.eval import EvalCase, EvalReport, run_eval
from teaagent.file_policy import DenyRule, FilePolicy, load_file_policy
from teaagent.graph_rag import GraphEdge, KnowledgeGraph, graph_retrieve
from teaagent.graphqlite_production import (
    GraphQLitePersistentStore,
    GraphQLiteProductionConfig,
)
from teaagent.graphqlite_store import (
    GraphQLiteConfig,
    GraphQLiteGraphStore,
    GraphQLiteRuntimeError,
    GraphQLiteUnavailableError,
    check_graphqlite_runtime,
    ensure_sqlite_extension_loading,
)
from teaagent.heartbeat import Heartbeat
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
from teaagent.policy import ApprovalPolicy, PermissionMode, parse_permission_mode
from teaagent.portability import (
    PortabilityResult,
    ProviderProfile,
    assess_provider_portability,
)
from teaagent.preflight import PreflightReport, preflight
from teaagent.prompt import PromptBundle, assemble_agent_prompt, parse_model_decision
from teaagent.rag import Document, InMemoryRetriever, agentic_retrieve
from teaagent.readiness import ReadinessReport, assess_managed_agent_readiness
from teaagent.run_store import RunStore, RunSummary
from teaagent.runner import (
    AgentRunner,
    ApprovalRequest,
    Decision,
    FinalAnswer,
    ToolRequest,
)
from teaagent.skill_loader import SkillContent, load_skills, skills_to_prompt_section
from teaagent.skill_review import SkillReviewResult, review_skill
from teaagent.stateless_mcp import (
    StatelessMCPRequest,
    StatelessMCPResponse,
    handle_stateless_tool_request,
)
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
    WorkspaceToolConfig,
    build_workspace_tool_registry,
    register_workspace_tools,
)

__all__ = [
    '__version__',
    'AIBOMManifest',
    'AgentRunner',
    'ApprovalPolicy',
    'ApprovalRequest',
    'AuditLogger',
    'ChatAgentConfig',
    'ChildProcessCodeModeBackend',
    'ClarificationResult',
    'CodeModeResult',
    'CodeModeSandbox',
    'ContainerCodeModeBackend',
    'ContextCompactor',
    'DPoPValidationResult',
    'Decision',
    'DenyRule',
    'Document',
    'FilePolicy',
    'EvalCase',
    'EvalReport',
    'FinalAnswer',
    'GraphEdge',
    'GraphQLiteConfig',
    'GraphQLiteGraphStore',
    'GraphQLitePersistentStore',
    'GraphQLiteProductionConfig',
    'GraphQLiteRuntimeError',
    'GraphQLiteUnavailableError',
    'HAS_CRYPTOGRAPHY',
    'HAS_OTEL',
    'Heartbeat',
    'InMemoryMetricsSink',
    'InMemoryOAuthStore',
    'InMemoryRetriever',
    'IntentScore',
    'InvalidClientError',
    'InvalidDPoPError',
    'InvalidGrantError',
    'JWTError',
    'KnowledgeGraph',
    'LLMConfigurationError',
    'LLMHTTPError',
    'LLMMessage',
    'LLMProviderError',
    'LLMRequest',
    'LLMResponse',
    'LLMResponseFormatError',
    'MCPClientError',
    'MCPHTTPClient',
    'register_mcp_tools',
    'MemoryCatalog',
    'MemoryEntry',
    'MetricSnapshot',
    'ModelConformanceReport',
    'ModelConformanceResult',
    'ModelDecisionEngine',
    'ModelRoute',
    'OTelAuditSink',
    'OTelMetricsSink',
    'OAuth21AuthorizationServer',
    'OAuth21Client',
    'OAuth21ResourceServer',
    'OAuth21TokenClaims',
    'OAuth21TokenResponse',
    'OAuthKeyRing',
    'OAuthStore',
    'PermissionMode',
    'PortabilityResult',
    'PreflightReport',
    'PromptBundle',
    'ProviderConfig',
    'ProviderProfile',
    'ReadinessReport',
    'RunBudget',
    'RunCancelledError',
    'RunStore',
    'RunSummary',
    'SQLiteOAuthStore',
    'SkillContent',
    'SkillReviewResult',
    'load_file_policy',
    'load_skills',
    'skills_to_prompt_section',
    'StatelessMCPRequest',
    'StatelessMCPResponse',
    'TelemetryConfig',
    'TelemetryNotAvailable',
    'ToolAnnotations',
    'ToolRateLimit',
    'ToolRegistry',
    'ToolRequest',
    'TraceRecorder',
    'TracingHTTPTransport',
    'UltraworkStore',
    'UnsafeCodeError',
    'WorkerRecord',
    'WebhookAuditSink',
    'WorkspaceToolConfig',
    'agentic_retrieve',
    'assemble_agent_prompt',
    'assess_managed_agent_readiness',
    'assess_provider_portability',
    'available_providers',
    'build_aibom',
    'build_mcp_http_server',
    'build_task_spec',
    'build_workspace_tool_registry',
    'check_graphqlite_runtime',
    'check_llm_configuration',
    'clarify_task',
    'classify_task',
    'compute_jwk_thumbprint',
    'compute_s256_challenge',
    'configure_metrics',
    'configure_telemetry',
    'create_jwt',
    'create_llm_adapter',
    'decode_jwt_unsafe',
    'ensure_sqlite_extension_loading',
    'execute_code_mode',
    'generate_code_verifier',
    'graph_retrieve',
    'handle_mcp_request',
    'handle_stateless_tool_request',
    'managed_runtime_context',
    'parse_model_decision',
    'parse_permission_mode',
    'preflight',
    'register_subagent_tool',
    'register_workspace_tools',
    'review_skill',
    'route_model',
    'run_chat_agent',
    'run_eval',
    'run_model_conformance',
    'serve_mcp_http',
    'serve_mcp_stdio',
    'verify_jwt',
]
