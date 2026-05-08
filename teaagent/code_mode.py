from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

ALLOWED_NODES = {
    ast.Add,
    ast.Assign,
    ast.BinOp,
    ast.Call,
    ast.Compare,
    ast.Constant,
    ast.Dict,
    ast.Div,
    ast.Eq,
    ast.Expr,
    ast.For,
    ast.Gt,
    ast.GtE,
    ast.If,
    ast.In,
    ast.List,
    ast.Load,
    ast.Lt,
    ast.LtE,
    ast.Mod,
    ast.Module,
    ast.Mult,
    ast.Name,
    ast.NotEq,
    ast.Store,
    ast.Sub,
    ast.Subscript,
    ast.Tuple,
    ast.UnaryOp,
    ast.USub,
}

SAFE_BUILTINS = {
    "abs": abs,
    "dict": dict,
    "enumerate": enumerate,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "round": round,
    "sorted": sorted,
    "str": str,
    "sum": sum,
}


@dataclass(frozen=True)
class CodeModeResult:
    variables: dict[str, Any]


class UnsafeCodeError(ValueError):
    pass


def execute_code_mode(code: str, *, inputs: dict[str, Any] | None = None) -> CodeModeResult:
    tree = ast.parse(code, mode="exec")
    _validate_tree(tree)
    namespace: dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
    if inputs:
        namespace.update(inputs)
    exec(compile(tree, "<teaagent-code-mode>", "exec"), namespace, namespace)
    variables = {key: value for key, value in namespace.items() if key != "__builtins__" and not key.startswith("_")}
    return CodeModeResult(variables=variables)


def _validate_tree(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if type(node) not in ALLOWED_NODES:
            raise UnsafeCodeError(f"Disallowed syntax: {type(node).__name__}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in SAFE_BUILTINS:
                raise UnsafeCodeError("Only approved builtin calls are allowed")
