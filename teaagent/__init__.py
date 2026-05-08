"""Governance-first agent harness."""

__version__ = '0.1.0'

from teaagent.aibom import AIBOMManifest, build_aibom
from teaagent.audit import AuditLogger
from teaagent.budget import RunBudget
from teaagent.chat_agent import (
    ChatAgentConfig,
    ModelDecisionEngine,
    register_subagent_tool,
    run_chat_agent,
)
from teaagent.code_mode import CodeModeResult, UnsafeCodeError, execute_code_mode
from teaagent.context import ContextCompactor
from teaagent.eval import EvalCase, EvalReport, run_eval
from teaagent.graph_rag import GraphEdge, KnowledgeGraph, graph_retrieve
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
    LLMRequest,
    LLMResponse,
    ProviderConfig,
    available_providers,
    check_llm_configuration,
    create_llm_adapter,
)
from teaagent.mcp_http import build_mcp_http_server, serve_mcp_http
from teaagent.mcp_server import handle_mcp_request, serve_mcp_stdio
from teaagent.memory import MemoryCatalog, MemoryEntry
from teaagent.model_routing import ModelRoute, classify_task, route_model
from teaagent.oauth21 import (
    HAS_CRYPTOGRAPHY,
    DPoPValidationResult,
    InvalidClientError,
    InvalidDPoPError,
    InvalidGrantError,
    JWTError,
    OAuth21AuthorizationServer,
    OAuth21Client,
    OAuth21ResourceServer,
    OAuth21TokenClaims,
    OAuth21TokenResponse,
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
from teaagent.skill_review import SkillReviewResult, review_skill
from teaagent.stateless_mcp import (
    StatelessMCPRequest,
    StatelessMCPResponse,
    handle_stateless_tool_request,
)
from teaagent.telemetry import (
    HAS_OTEL,
    OTelAuditSink,
    TelemetryConfig,
    TelemetryNotAvailable,
    TracingHTTPTransport,
    configure_telemetry,
)
from teaagent.tools import ToolAnnotations, ToolRegistry
from teaagent.trace import TraceRecorder
from teaagent.ultrawork import UltraworkStore, WorkerRecord
from teaagent.workspace_tools import (
    WorkspaceToolConfig,
    build_workspace_tool_registry,
    register_workspace_tools,
)

__all__ = [
    'AIBOMManifest',
    'AgentRunner',
    'ApprovalPolicy',
    'ApprovalRequest',
    'AuditLogger',
    'ChatAgentConfig',
    'ClarificationResult',
    'CodeModeResult',
    'ContextCompactor',
    'Decision',
    'Document',
    'EvalCase',
    'EvalReport',
    'FinalAnswer',
    'GraphEdge',
    'GraphQLiteConfig',
    'GraphQLiteGraphStore',
    'GraphQLiteRuntimeError',
    'GraphQLiteUnavailableError',
    'Heartbeat',
    'InMemoryRetriever',
    'IntentScore',
    'KnowledgeGraph',
    'LLMConfigurationError',
    'LLMHTTPError',
    'LLMMessage',
    'LLMRequest',
    'LLMResponse',
    'MemoryCatalog',
    'MemoryEntry',
    'ModelRoute',
    'ModelDecisionEngine',
    'PermissionMode',
    'PortabilityResult',
    'PreflightReport',
    'PromptBundle',
    'ProviderProfile',
    'ProviderConfig',
    'ReadinessReport',
    'RunBudget',
    'RunStore',
    'RunSummary',
    'SkillReviewResult',
    'StatelessMCPRequest',
    'StatelessMCPResponse',
    'ToolAnnotations',
    'ToolRegistry',
    'ToolRequest',
    'TraceRecorder',
    'UltraworkStore',
    'UnsafeCodeError',
    'WorkerRecord',
    'WorkspaceToolConfig',
    'HAS_OTEL',
    'OTelAuditSink',
    'TelemetryConfig',
    'TelemetryNotAvailable',
    'TracingHTTPTransport',
    'configure_telemetry',
    'agentic_retrieve',
    'assess_managed_agent_readiness',
    'assess_provider_portability',
    'available_providers',
    'assemble_agent_prompt',
    'build_aibom',
    'build_mcp_http_server',
    'build_task_spec',
    'HAS_CRYPTOGRAPHY',
    'DPoPValidationResult',
    'InvalidClientError',
    'InvalidDPoPError',
    'InvalidGrantError',
    'JWTError',
    'OAuth21AuthorizationServer',
    'OAuth21Client',
    'OAuth21ResourceServer',
    'OAuth21TokenClaims',
    'OAuth21TokenResponse',
    'compute_jwk_thumbprint',
    'compute_s256_challenge',
    'create_jwt',
    'decode_jwt_unsafe',
    'generate_code_verifier',
    'verify_jwt',
    'build_workspace_tool_registry',
    'check_graphqlite_runtime',
    'check_llm_configuration',
    'clarify_task',
    'classify_task',
    'create_llm_adapter',
    'execute_code_mode',
    'ensure_sqlite_extension_loading',
    'graph_retrieve',
    'handle_mcp_request',
    'handle_stateless_tool_request',
    'parse_model_decision',
    'parse_permission_mode',
    'preflight',
    'review_skill',
    'route_model',
    'register_subagent_tool',
    'register_workspace_tools',
    'serve_mcp_http',
    'serve_mcp_stdio',
    'run_chat_agent',
    'run_eval',
]
