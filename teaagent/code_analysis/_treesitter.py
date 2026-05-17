from __future__ import annotations

import ast
import contextlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_EXT_LANGUAGE = {
    '.py': 'python',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'tsx',
    '.go': 'go',
    '.rs': 'rust',
    '.java': 'java',
    '.c': 'c',
    '.h': 'c',
    '.cc': 'cpp',
    '.cpp': 'cpp',
    '.cxx': 'cpp',
    '.hpp': 'cpp',
    '.cs': 'c_sharp',
    '.php': 'php',
    '.rb': 'ruby',
}


@dataclass(frozen=True)
class CodeRelation:
    source: str
    relation: str
    target: str
    line: int
    column: int


def extract_tree_sitter_relations(path: str) -> list[CodeRelation]:
    source_path = Path(path)
    language = _EXT_LANGUAGE.get(source_path.suffix.lower())
    if language is None:
        return []
    if language == 'python':
        with contextlib.suppress(RuntimeError):
            _try_tree_sitter_parse(source_path, language)
        return _extract_python_relations(source_path)
    return _extract_generic_tree_sitter_relations(source_path, language)


def _extract_python_relations(path: Path) -> list[CodeRelation]:
    text = path.read_text(encoding='utf-8')
    tree = ast.parse(text)
    relations: list[CodeRelation] = []
    module_name = path.stem
    # The module itself is the initial scope.
    scope_stack: list[str] = [module_name]

    class Visitor(ast.NodeVisitor):
        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                target = alias.name
                relations.append(
                    CodeRelation(
                        source=scope_stack[-1],
                        relation='imports',
                        target=target,
                        line=node.lineno,
                        column=node.col_offset + 1,
                    )
                )

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            module = node.module or ''
            for alias in node.names:
                target = f'{module}.{alias.name}' if module else alias.name
                relations.append(
                    CodeRelation(
                        source=scope_stack[-1],
                        relation='imports',
                        target=target,
                        line=node.lineno,
                        column=node.col_offset + 1,
                    )
                )

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            # Avoid redundant module prefix if it's already the top of the stack
            fn_name = f'{scope_stack[-1]}.{node.name}'
            relations.append(
                CodeRelation(
                    source=scope_stack[-1],
                    relation='defines',
                    target=fn_name,
                    line=node.lineno,
                    column=node.col_offset + 1,
                )
            )
            scope_stack.append(fn_name)
            self.generic_visit(node)
            scope_stack.pop()

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            fn_name = f'{scope_stack[-1]}.{node.name}'
            relations.append(
                CodeRelation(
                    source=scope_stack[-1],
                    relation='defines',
                    target=fn_name,
                    line=node.lineno,
                    column=node.col_offset + 1,
                )
            )
            scope_stack.append(fn_name)
            self.generic_visit(node)
            scope_stack.pop()

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            class_name = f'{scope_stack[-1]}.{node.name}'
            relations.append(
                CodeRelation(
                    source=scope_stack[-1],
                    relation='defines',
                    target=class_name,
                    line=node.lineno,
                    column=node.col_offset + 1,
                )
            )
            for base in node.bases:
                base_name = _name_from_expr(base)
                if base_name:
                    relations.append(
                        CodeRelation(
                            source=class_name,
                            relation='inherits',
                            target=base_name,
                            line=node.lineno,
                            column=node.col_offset + 1,
                        )
                    )
            scope_stack.append(class_name)
            self.generic_visit(node)
            scope_stack.pop()

        def visit_Call(self, node: ast.Call) -> None:
            call_target = _name_from_expr(node.func)
            if call_target:
                relations.append(
                    CodeRelation(
                        source=scope_stack[-1],
                        relation='calls',
                        target=call_target,
                        line=node.lineno,
                        column=node.col_offset + 1,
                    )
                )
            self.generic_visit(node)

    Visitor().visit(tree)
    return relations


def _name_from_expr(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _name_from_expr(node.value)
        if left:
            return f'{left}.{node.attr}'
        return node.attr
    if isinstance(node, ast.Call):
        return _name_from_expr(node.func)
    return ''


def _try_tree_sitter_parse(path: Path, language: str) -> Any:
    try:
        from tree_sitter_language_pack import (
            get_parser,  # type: ignore[import-not-found]
        )
    except ImportError as exc:
        raise RuntimeError(
            'tree-sitter parser is required for recognized file types'
        ) from exc
    try:
        parser = get_parser(language)
        tree = parser.parse(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise RuntimeError(f'failed to parse {path} with tree-sitter') from exc
    if tree is None or tree.root_node() is None:
        raise RuntimeError(f'failed to parse {path} with tree-sitter')
    return tree


def _extract_generic_tree_sitter_relations(
    path: Path, language: str
) -> list[CodeRelation]:
    tree = _try_tree_sitter_parse(path, language)
    content = path.read_bytes()
    root = tree.root_node()
    relations: list[CodeRelation] = []
    scope = path.stem
    stack = [root]
    while stack:
        node = stack.pop()
        node_type = str(getattr(node, 'type', '')).lower()
        if 'import' in node_type:
            target = _best_node_text(node, content)
            if target:
                line, col = _node_position(node)
                relations.append(
                    CodeRelation(
                        source=scope,
                        relation='imports',
                        target=target,
                        line=line,
                        column=col,
                    )
                )
        elif (
            'class' in node_type
            or 'interface' in node_type
            or 'function' in node_type
            or 'method' in node_type
        ):
            name = _extract_decl_name(node, content)
            if name:
                line, col = _node_position(node)
                relations.append(
                    CodeRelation(
                        source=scope,
                        relation='defines',
                        target=name,
                        line=line,
                        column=col,
                    )
                )
        elif 'call' in node_type:
            target = _extract_call_target(node, content)
            if target:
                line, col = _node_position(node)
                relations.append(
                    CodeRelation(
                        source=scope,
                        relation='calls',
                        target=target,
                        line=line,
                        column=col,
                    )
                )
        for child in reversed(getattr(node, 'children', [])):
            stack.append(child)
    return relations


def _node_position(node: object) -> tuple[int, int]:
    start_point = getattr(node, 'start_point', (0, 0))
    if isinstance(start_point, tuple) and len(start_point) == 2:
        return int(start_point[0]) + 1, int(start_point[1]) + 1
    return 1, 1


def _node_text(node: object, content: bytes) -> str:
    start = int(getattr(node, 'start_byte', 0))
    end = int(getattr(node, 'end_byte', start))
    if end <= start:
        return ''
    return content[start:end].decode('utf-8', errors='ignore').strip()


def _best_node_text(node: object, content: bytes) -> str:
    text = _node_text(node, content)
    if text:
        return text.replace('\n', ' ')
    for child in getattr(node, 'children', []):
        child_text = _node_text(child, content)
        if child_text:
            return child_text.replace('\n', ' ')
    return ''


def _extract_decl_name(node: object, content: bytes) -> str:
    for child in getattr(node, 'children', []):
        node_type = str(getattr(child, 'type', '')).lower()
        if node_type in {'identifier', 'type_identifier', 'property_identifier'}:
            return _node_text(child, content)
    return _best_node_text(node, content)


def _extract_call_target(node: object, content: bytes) -> str:
    for child in getattr(node, 'children', []):
        node_type = str(getattr(child, 'type', '')).lower()
        if node_type in {
            'identifier',
            'field_identifier',
            'property_identifier',
            'scoped_identifier',
            'member_expression',
            'attribute',
        }:
            text = _node_text(child, content)
            if text:
                return text
    return _best_node_text(node, content)
