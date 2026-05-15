"""Policy-as-Code — declarative deny rules loaded from ``policy.yaml``.

``FilePolicy`` loads a YAML (or JSON) policy file and evaluates ``DenyRule``
entries *before* ``ApprovalPolicy`` is consulted.  Rules are matched in order;
the first matching rule's action wins.

Rule schema (``policy.yaml``)::

    version: 1
    rules:
      - id: block-rm-rf
        description: Never allow unconditional recursive deletes
        tool_pattern: "workspace_run_shell_*"
        argument_pattern:
          command: "rm -rf"
        action: deny
        message: "Recursive delete is blocked by policy."

      - id: limit-prod-writes
        description: Block writes to paths matching prod_*
        tool_pattern: "workspace_write_file"
        argument_pattern:
          path: "prod_*"
        action: deny
        message: "Writes to prod_* paths require manual review."

Fields:

``tool_pattern``
    A glob-style pattern matched against the tool name (``fnmatch``).
    Use ``*`` to match all tools.

``argument_pattern``
    An optional mapping of argument-key → value pattern.  The value is matched
    with ``fnmatch`` after converting the actual argument value to a string.
    All listed keys must match for the rule to fire.

``action``
    ``deny`` — raise ``ToolPermissionError`` and block the call.
    (``allow`` is reserved for future allow-override semantics.)

``message``
    Human-readable reason shown to the user on denial.

Loading::

    from teaagent.file_policy import FilePolicy, load_file_policy

    policy = load_file_policy(root='/path/to/project')
    policy.assert_allowed(tool_name='workspace_run_shell_mutate',
                          arguments={'command': 'rm -rf /'})
"""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from teaagent.errors import ToolPermissionError

_POLICY_FILENAMES = ('policy.yaml', 'policy.yml', 'policy.json')
_SUPPORTED_VERSION = 1


@dataclass(frozen=True)
class DenyRule:
    """A single declarative deny rule."""

    id: str
    tool_pattern: str
    action: str = 'deny'
    argument_pattern: dict[str, str] = field(default_factory=dict)
    description: str = ''
    message: str = ''

    def matches(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        """Return True if this rule applies to the given tool call."""
        if not fnmatch.fnmatch(tool_name, self.tool_pattern):
            return False
        for arg_key, arg_pattern in self.argument_pattern.items():
            actual = arguments.get(arg_key)
            if actual is None:
                return False
            if not fnmatch.fnmatch(str(actual), arg_pattern):
                return False
        return True


@dataclass(frozen=True)
class FilePolicy:
    """Evaluated policy loaded from a ``policy.yaml`` file.

    Call ``assert_allowed`` before dispatching any tool call to enforce deny
    rules declared in the policy file.
    """

    rules: list[DenyRule] = field(default_factory=list)
    source_path: Optional[Path] = None

    def assert_allowed(self, *, tool_name: str, arguments: dict[str, Any]) -> None:
        """Raise ``ToolPermissionError`` if any deny rule matches.

        Parameters
        ----------
        tool_name:
            The name of the tool about to be executed.
        arguments:
            The arguments that will be passed to the tool.
        """
        for rule in self.rules:
            if rule.action != 'deny':
                continue
            if rule.matches(tool_name, arguments):
                reason = rule.message or f"Blocked by policy rule '{rule.id}'."
                raise ToolPermissionError(reason)


def _parse_rules(raw_rules: list[Any]) -> list[DenyRule]:
    rules: list[DenyRule] = []
    for entry in raw_rules:
        if not isinstance(entry, dict):
            continue
        rule_id = str(entry.get('id', ''))
        tool_pattern = str(entry.get('tool_pattern', '*'))
        action = str(entry.get('action', 'deny')).lower()
        argument_pattern: dict[str, str] = {}
        raw_ap = entry.get('argument_pattern')
        if isinstance(raw_ap, dict):
            argument_pattern = {str(k): str(v) for k, v in raw_ap.items()}
        description = str(entry.get('description', ''))
        message = str(entry.get('message', ''))
        rules.append(
            DenyRule(
                id=rule_id,
                tool_pattern=tool_pattern,
                action=action,
                argument_pattern=argument_pattern,
                description=description,
                message=message,
            )
        )
    return rules


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ''
    if value[0] == value[-1] and value.startswith(("'", '"')):
        return value[1:-1]
    if value.lower() in {'true', 'false'}:
        return value.lower() == 'true'
    try:
        return int(value)
    except ValueError:
        return value


def _load_simple_policy_yaml(text: str) -> dict[str, Any]:
    """Parse the small policy.yaml subset supported without PyYAML.

    The project keeps runtime dependencies to the standard library. This parser
    intentionally supports only the policy schema documented above: top-level
    scalars plus a ``rules`` list of mappings with optional one-level
    ``argument_pattern`` mappings.
    """
    data: dict[str, Any] = {}
    current_rule: Optional[dict[str, Any]] = None
    nested_key: Optional[str] = None

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith('#'):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(' '))
        line = raw_line.strip()

        if indent == 0:
            current_rule = None
            nested_key = None
            key, sep, value = line.partition(':')
            if not sep:
                raise ValueError('policy YAML line must contain ":"')
            key = key.strip()
            if key == 'rules' and not value.strip():
                data[key] = []
            else:
                data[key] = _parse_scalar(value)
            continue

        if indent == 2 and line.startswith('- '):
            rule_data = line[2:].strip()
            current_rule = {}
            nested_key = None
            data.setdefault('rules', []).append(current_rule)
            if rule_data:
                key, sep, value = rule_data.partition(':')
                if not sep:
                    raise ValueError('policy rule line must contain ":"')
                current_rule[key.strip()] = _parse_scalar(value)
            continue

        if current_rule is None:
            raise ValueError('policy YAML nested value must appear under rules')

        key, sep, value = line.partition(':')
        if not sep:
            raise ValueError('policy YAML line must contain ":"')
        key = key.strip()
        value = value.strip()
        if indent == 4:
            if value:
                current_rule[key] = _parse_scalar(value)
                nested_key = None
            else:
                current_rule[key] = {}
                nested_key = key
            continue

        if indent == 6 and nested_key is not None:
            nested = current_rule.setdefault(nested_key, {})
            if not isinstance(nested, dict):
                raise ValueError(f'policy YAML key {nested_key!r} must be a mapping')
            nested[key] = _parse_scalar(value)
            continue

        raise ValueError(f'unsupported policy YAML indentation: {indent}')

    return data


def _load_policy_dict(path: Path) -> dict[str, Any]:
    """Load a policy file (YAML or JSON) and return its contents as a dict."""
    text = path.read_text(encoding='utf-8')
    if path.suffix in {'.yaml', '.yml'}:
        try:
            import yaml  # type: ignore[import-untyped]

            data = yaml.safe_load(text)
        except ImportError:
            data = _load_simple_policy_yaml(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f'policy file {path} must contain a mapping at the top level')
    return data


def load_file_policy(
    root: str | Path,
    *,
    filename: Optional[str] = None,
) -> FilePolicy:
    """Discover and load a policy file under *root*.

    Searches for ``policy.yaml``, ``policy.yml``, or ``policy.json`` in:
    1. ``<root>/.teaagent/``
    2. ``<root>/``

    Returns an empty ``FilePolicy`` (no rules) when no file is found.

    Parameters
    ----------
    root:
        Workspace root directory.
    filename:
        Override the filename to search for instead of the defaults.
    """
    root_path = Path(root).resolve()
    search_names = (filename,) if filename else _POLICY_FILENAMES
    search_dirs = [root_path / '.teaagent', root_path]

    for search_dir in search_dirs:
        for name in search_names:
            candidate = search_dir / name
            if candidate.is_file():
                data = _load_policy_dict(candidate)
                version = data.get('version', 1)
                if int(version) != _SUPPORTED_VERSION:
                    raise ValueError(
                        f'unsupported policy version {version!r} in {candidate}'
                    )
                raw_rules = data.get('rules', [])
                rules = _parse_rules(raw_rules if isinstance(raw_rules, list) else [])
                return FilePolicy(rules=rules, source_path=candidate)

    return FilePolicy()
