"""Governance-first agent harness."""

__version__ = "0.1.0"

from teaagent.aibom import AIBOMManifest, build_aibom
from teaagent.audit import AuditLogger
from teaagent.budget import RunBudget
from teaagent.chat_agent import ChatAgentConfig, ModelDecisionEngine, run_chat_agent
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
from teaagent.intent import ClarificationResult, IntentScore, build_task_spec, clarify_task
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
from teaagent.memory import MemoryCatalog, MemoryEntry
from teaagent.policy import ApprovalPolicy, PermissionMode, parse_permission_mode
from teaagent.prompt import PromptBundle, assemble_agent_prompt, parse_model_decision
from teaagent.portability import ProviderProfile, PortabilityResult, assess_provider_portability
from teaagent.rag import Document, InMemoryRetriever, agentic_retrieve
from teaagent.readiness import ReadinessReport, assess_managed_agent_readiness
from teaagent.runner import AgentRunner, Decision, FinalAnswer, ToolRequest
from teaagent.run_store import RunStore, RunSummary
from teaagent.skill_review import SkillReviewResult, review_skill
from teaagent.stateless_mcp import StatelessMCPRequest, StatelessMCPResponse, handle_stateless_tool_request
from teaagent.tools import ToolAnnotations, ToolRegistry
from teaagent.trace import TraceRecorder
from teaagent.workspace_tools import WorkspaceToolConfig, build_workspace_tool_registry, register_workspace_tools

__all__ = [
    "AIBOMManifest",
    "AgentRunner",
    "ApprovalPolicy",
    "AuditLogger",
    "ChatAgentConfig",
    "ClarificationResult",
    "CodeModeResult",
    "ContextCompactor",
    "Decision",
    "Document",
    "EvalCase",
    "EvalReport",
    "FinalAnswer",
    "GraphEdge",
    "GraphQLiteConfig",
    "GraphQLiteGraphStore",
    "GraphQLiteRuntimeError",
    "GraphQLiteUnavailableError",
    "InMemoryRetriever",
    "IntentScore",
    "KnowledgeGraph",
    "LLMConfigurationError",
    "LLMHTTPError",
    "LLMMessage",
    "LLMRequest",
    "LLMResponse",
    "MemoryCatalog",
    "MemoryEntry",
    "ModelDecisionEngine",
    "PermissionMode",
    "PortabilityResult",
    "PromptBundle",
    "ProviderProfile",
    "ProviderConfig",
    "ReadinessReport",
    "RunBudget",
    "RunStore",
    "RunSummary",
    "SkillReviewResult",
    "StatelessMCPRequest",
    "StatelessMCPResponse",
    "ToolAnnotations",
    "ToolRegistry",
    "ToolRequest",
    "TraceRecorder",
    "UnsafeCodeError",
    "WorkspaceToolConfig",
    "agentic_retrieve",
    "assess_managed_agent_readiness",
    "assess_provider_portability",
    "available_providers",
    "assemble_agent_prompt",
    "build_aibom",
    "build_task_spec",
    "build_workspace_tool_registry",
    "check_graphqlite_runtime",
    "check_llm_configuration",
    "clarify_task",
    "create_llm_adapter",
    "execute_code_mode",
    "ensure_sqlite_extension_loading",
    "graph_retrieve",
    "handle_stateless_tool_request",
    "parse_model_decision",
    "parse_permission_mode",
    "review_skill",
    "register_workspace_tools",
    "run_chat_agent",
    "run_eval",
]
