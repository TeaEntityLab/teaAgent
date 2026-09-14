"""Code ontology for AST-based code structure graph.

This module provides tools for extracting code structure from source files
and building a knowledge graph of classes, functions, modules, and their relationships.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class CodeNode:
    """Represents a code entity in the ontology graph."""

    node_id: str
    node_type: str  # 'Module', 'Class', 'Function', 'Method', 'Variable'
    name: str
    file_path: str
    line_number: int
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            'node_id': self.node_id,
            'node_type': self.node_type,
            'name': self.name,
            'file_path': self.file_path,
            'line_number': self.line_number,
            **self.metadata,
        }


@dataclass(frozen=True)
class CodeEdge:
    """Represents a relationship between code entities."""

    source: str
    target: str
    edge_type: str  # 'CALLS', 'INHERITS', 'IMPORTS', 'CONTAINS', 'DEFINES'
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            'source': self.source,
            'target': self.target,
            'edge_type': self.edge_type,
            **self.metadata,
        }


class CodeOntologyGraph:
    """Manages code ontology graph with GraphQLite integration."""

    def __init__(self, root: str | Path, graph_store: Optional[Any] = None) -> None:
        """Initialize code ontology graph.

        Args:
            root: Root directory for code analysis
            graph_store: Optional GraphQLite graph store instance for persistence.
                        Must have .graph.upsert_node(), .graph.upsert_edge(), and .query() methods.
        """
        self.root = Path(root).resolve()
        self.graph_store = graph_store
        self.builder = CodeOntologyBuilder(root)

    def build(self, extensions: Optional[list[str]] = None) -> None:
        """Build code ontology from source files."""
        self.builder.build_from_directory(extensions)
        self._resolve_call_targets()

        if self.graph_store:
            self._sync_to_graph_store()

    def _resolve_call_targets(self) -> None:
        """Rewrite wildcard CALLS targets to real function node IDs.

        visit_Call emits ``function:*:name:*`` placeholders. Resolve them to
        the actual ``function:path:name:line`` node IDs by name lookup.
        Ambiguous names (same name in multiple files) resolve to the first
        match — a known limitation of name-only resolution.
        """
        # Build name → node_id index for Function/Method nodes.
        name_to_id: dict[str, str] = {}
        for node in self.builder.get_nodes():
            if node.node_type in ('Function', 'Method'):
                name_to_id.setdefault(node.name, node.node_id)

        resolved: list[CodeEdge] = []
        for edge in self.builder.get_edges():
            if edge.edge_type == 'CALLS' and ':*:' in edge.target:
                # Extract the function name from function:*:name:*
                parts = edge.target.split(':')
                if len(parts) >= 3:
                    name = parts[2]
                    real_id = name_to_id.get(name)
                    if real_id:
                        resolved.append(
                            CodeEdge(
                                source=edge.source,
                                target=real_id,
                                edge_type=edge.edge_type,
                                metadata=edge.metadata,
                            )
                        )
                        continue
            resolved.append(edge)
        self.builder.edges = resolved

    def _sync_to_graph_store(self) -> None:
        """Sync nodes and edges to GraphQLite graph store."""
        if self.graph_store is None:
            return
        graph = self.graph_store.graph
        nodes = [
            (node.node_id, node.to_dict(), node.node_type)
            for node in self.builder.get_nodes()
        ]
        edges = [
            (edge.source, edge.target, edge.to_dict(), edge.edge_type)
            for edge in self.builder.get_edges()
        ]
        # Bulk insert requires both endpoints to exist. Create stub nodes
        # for edge targets that reference external modules (e.g. stdlib
        # imports like `os`, `sys`) not parsed as source files.
        known_ids = {n[0] for n in nodes}
        for source, target, _props, _rel in edges:
            for endpoint in (source, target):
                if endpoint not in known_ids:
                    stub_name = endpoint.split(':')[-1] or endpoint
                    nodes.append(
                        (endpoint, {'name': stub_name, 'external': True}, 'External')
                    )
        # Bulk insert: one transaction instead of per-node/edge SQLite writes.
        # Falls back to per-item upsert if the store doesn't support bulk.
        if hasattr(graph, 'insert_graph_bulk'):
            graph.insert_graph_bulk(nodes, edges)
        else:
            for node_id, props, label in nodes:
                graph.upsert_node(node_id, props, label=label)
            for source, target, props, rel_type in edges:
                graph.upsert_edge(source, target, props, rel_type=rel_type)

    def query_dependencies(
        self, entity_name: str, direction: str = 'both'
    ) -> list[dict[str, Any]]:
        """Query dependency chains for a code entity.

        Args:
            entity_name: Name of the entity (class, function, etc.)
            direction: 'upstream' (callers), 'downstream' (callees), or 'both'

        Returns:
            List of related entities with their relationships.
        """
        if not self.graph_store:
            return []

        params: dict[str, Any] = {'entity_name': entity_name}
        if direction == 'upstream':
            cypher = """
            MATCH (e {name: $entity_name})<-[:CALLS]-(caller)
            RETURN caller.name, caller.node_type, caller.file_path
            """
        elif direction == 'downstream':
            cypher = """
            MATCH (e {name: $entity_name})-[:CALLS]->(callee)
            RETURN callee.name, callee.node_type, callee.file_path
            """
        else:  # both
            cypher = """
            MATCH (e {name: $entity_name})
            OPTIONAL MATCH (e)<-[:CALLS]-(caller)
            OPTIONAL MATCH (e)-[:CALLS]->(callee)
            RETURN
                COALESCE(caller.name, callee.name) as name,
                COALESCE(caller.node_type, callee.node_type) as node_type,
                COALESCE(caller.file_path, callee.file_path) as file_path
            """

        results = self.graph_store.query(cypher, params=params)
        # OPTIONAL MATCH produces a row of nulls when the entity exists but
        # has no edges in that direction — drop them so callers see [] not
        # [{name: null, ...}]. Check all key variants: 'name' (both),
        # 'caller.name' (upstream), 'callee.name' (downstream).
        return [
            r
            for r in results
            if r.get('name') is not None
            or r.get('caller.name') is not None
            or r.get('callee.name') is not None
        ]

    def query_inheritance_chain(self, class_name: str) -> list[dict[str, Any]]:
        """Query inheritance hierarchy for a class.

        Args:
            class_name: Name of the class

        Returns:
            List of classes in the inheritance chain.
        """
        if not self.graph_store:
            return []

        cypher = """
        MATCH (c:Class {name: $class_name})
        MATCH path = (c)-[:INHERITS*]->(ancestor:Class)
        RETURN ancestor.name, ancestor.file_path
        """

        return self.graph_store.query(cypher, params={'class_name': class_name})

    def query_module_structure(self, file_path: str) -> list[dict[str, Any]]:
        """Query all entities in a module.

        Args:
            file_path: Path to the module file

        Returns:
            List of classes and functions in the module.
        """
        if not self.graph_store:
            return []

        cypher = """
        MATCH (m:Module {file_path: $file_path})-[:CONTAINS]->(entity)
        RETURN entity.name, entity.node_type, entity.line_number
        ORDER BY entity.line_number
        """

        return self.graph_store.query(cypher, params={'file_path': file_path})


class CodeOntologyBuilder:
    """Builds code ontology graph from source files."""

    def __init__(self, root: str | Path) -> None:
        """Initialize code ontology builder.

        Args:
            root: Root directory for code analysis
        """
        self.root = Path(root).resolve()
        self.nodes: list[CodeNode] = []
        self.edges: list[CodeEdge] = []

    def build_from_directory(self, extensions: Optional[list[str]] = None) -> None:
        """Build ontology from all source files in directory.

        Args:
            extensions: File extensions to parse (e.g., ['.py', '.js']).
        """
        if extensions is None:
            extensions = ['.py']

        # Skip dependency caches, virtualenvs, and vendored trees — they
        # produce thousands of noise nodes and drown out the project source.
        _EXCLUDE_DIRS = {
            '.git',
            '.hg',
            '.svn',
            '.tox',
            '.venv',
            'venv',
            'env',
            'node_modules',
            '__pycache__',
            '.mypy_cache',
            '.pytest_cache',
            '.ruff_cache',
            '.uv-cache',
            '.teaagent',
            'dist',
            'build',
            '.eggs',
            '*.egg-info',
        }

        for ext in extensions:
            for file_path in self.root.rglob(f'*{ext}'):
                # Skip files inside excluded directories.
                if any(
                    part in _EXCLUDE_DIRS or part.endswith('.egg-info')
                    for part in file_path.relative_to(self.root).parts
                ):
                    continue
                self._parse_file(file_path)

    def _parse_file(self, file_path: Path) -> None:
        """Parse a single source file and extract code structure."""
        try:
            content = file_path.read_text(encoding='utf-8')
            tree = ast.parse(content, filename=str(file_path))

            # Create module node
            module_id = f'module:{file_path.relative_to(self.root)}'
            module_node = CodeNode(
                node_id=module_id,
                node_type='Module',
                name=file_path.stem,
                file_path=str(file_path.relative_to(self.root)),
                line_number=1,
                metadata={'language': self._detect_language(file_path)},
            )
            self.nodes.append(module_node)

            # Extract classes and functions
            visitor = CodeOntologyVisitor(
                str(file_path.relative_to(self.root)), module_id
            )
            visitor.visit(tree)

            self.nodes.extend(visitor.nodes)
            self.edges.extend(visitor.edges)

        except (SyntaxError, UnicodeDecodeError, OSError):
            # Skip files that can't be parsed
            pass

    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        ext = file_path.suffix.lower()
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.c': 'c',
        }
        return language_map.get(ext, 'unknown')

    def get_nodes(self) -> list[CodeNode]:
        return self.nodes

    def get_edges(self) -> list[CodeEdge]:
        return self.edges


class CodeOntologyVisitor(ast.NodeVisitor):
    """AST visitor for extracting code structure."""

    def __init__(self, file_path: str, module_id: str) -> None:
        """Initialize AST visitor for code structure extraction.

        Args:
            file_path: Path to the source file being analyzed
            module_id: Unique identifier for the module
        """
        self.file_path = file_path
        self.module_id = module_id
        self.nodes: list[CodeNode] = []
        self.edges: list[CodeEdge] = []
        self.current_class: Optional[str] = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        class_id = f'class:{self.file_path}:{node.name}:{node.lineno}'

        # Extract base classes
        base_classes: list[str] = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_classes.append(base.id)
            elif isinstance(base, ast.Attribute):
                base_classes.append(ast.unparse(base))

        class_node = CodeNode(
            node_id=class_id,
            node_type='Class',
            name=node.name,
            file_path=self.file_path,
            line_number=node.lineno,
            metadata={
                'bases': base_classes,
                'docstring': ast.get_docstring(node),
            },
        )
        self.nodes.append(class_node)

        # Edge: Module contains Class
        self.edges.append(
            CodeEdge(
                source=self.module_id,
                target=class_id,
                edge_type='CONTAINS',
                metadata={},
            )
        )

        # Edges: Class inherits from base classes
        for base in base_classes:  # type: ignore[assignment]
            self.edges.append(
                CodeEdge(
                    source=class_id,
                    target=f'class:*:{base}:*',
                    edge_type='INHERITS',
                    metadata={'base_class': base},
                )
            )

        # Visit class body with current class context
        old_class = self.current_class
        self.current_class = class_id
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        function_id = f'function:{self.file_path}:{node.name}:{node.lineno}'
        node_type = 'Method' if self.current_class else 'Function'

        function_node = CodeNode(
            node_id=function_id,
            node_type=node_type,
            name=node.name,
            file_path=self.file_path,
            line_number=node.lineno,
            metadata={
                'args': [arg.arg for arg in node.args.args],
                'returns': ast.unparse(node.returns) if node.returns else None,
                'docstring': ast.get_docstring(node),
                'is_async': isinstance(node, ast.AsyncFunctionDef),
            },
        )
        self.nodes.append(function_node)

        # Edge: Module/Class contains Function/Method
        container_id = self.current_class if self.current_class else self.module_id
        self.edges.append(
            CodeEdge(
                source=container_id,
                target=function_id,
                edge_type='CONTAINS',
                metadata={},
            )
        )

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            import_id = f'module:{alias.name}'
            self.edges.append(
                CodeEdge(
                    source=self.module_id,
                    target=import_id,
                    edge_type='IMPORTS',
                    metadata={'alias': alias.asname},
                )
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ''
        for alias in node.names:
            target_id = (
                f'module:{module}.{alias.name}' if module else f'module:{alias.name}'
            )
            self.edges.append(
                CodeEdge(
                    source=self.module_id,
                    target=target_id,
                    edge_type='IMPORTS',
                    metadata={
                        'from_module': module,
                        'alias': alias.asname,
                    },
                )
            )

    def visit_Call(self, node: ast.Call) -> None:
        # Extract function call
        if isinstance(node.func, ast.Name):
            target_id = f'function:*:{node.func.id}:*'
        elif isinstance(node.func, ast.Attribute):
            target_id = f'function:*:{ast.unparse(node.func)}:*'
        else:
            target_id = f'function:*:{ast.unparse(node.func)}:*'

        # Find the containing function
        containing_function = None
        for func_node in reversed(self.nodes):
            if func_node.node_type in ('Function', 'Method'):
                containing_function = func_node.node_id
                break

        if containing_function:
            self.edges.append(
                CodeEdge(
                    source=containing_function,
                    target=target_id,
                    edge_type='CALLS',
                    metadata={'line': node.lineno},
                )
            )

        self.generic_visit(node)
