"""Factory for creating backend adapters."""

from typing import Any
from teaagent.external_backends.adapter import BackendAdapter, BackendConfig
from teaagent.external_backends.knowledge import KnowledgeSearchBackend
from teaagent.external_backends.code_parse import CodeParseBackend


class BackendAdapterFactory:
    """Factory for creating backend adapters."""
    
    @staticmethod
    def create_knowledge_backend(
        backend_type: str,
        config: BackendConfig,
    ) -> KnowledgeSearchBackend:
        """Create knowledge backend adapter.
        
        Args:
            backend_type: Type of backend to create
            config: Backend configuration
            
        Returns:
            Knowledge search backend instance
            
        Raises:
            ValueError: If backend type is unknown
        """
        if backend_type == 'local':
            from teaagent.external_backends.local import LocalKnowledgeAdapter
            return LocalKnowledgeAdapter(config)
        elif backend_type == 'qmd':
            from teaagent.external_backends.qmd import QmdMcpAdapter
            return QmdMcpAdapter(config)
        else:
            raise ValueError(f'Unknown knowledge backend type: {backend_type}')
    
    @staticmethod
    def create_code_parse_backend(
        backend_type: str,
        config: BackendConfig,
    ) -> CodeParseBackend:
        """Create code parse backend adapter.
        
        Args:
            backend_type: Type of backend to create
            config: Backend configuration
            
        Returns:
            Code parse backend instance
            
        Raises:
            ValueError: If backend type is unknown
        """
        if backend_type == 'tree-sitter':
            from teaagent.external_backends.tree_sitter import TreeSitterAdapter
            return TreeSitterAdapter(config)
        else:
            raise ValueError(f'Unknown code parse backend type: {backend_type}')
