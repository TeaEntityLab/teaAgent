"""Tests for pre/post action hooks."""

from __future__ import annotations

import unittest
from pathlib import Path

from teaagent.hooks import (
    HookConfig,
    HookError,
    HookRegistry,
    shell_command_hook,
)
from teaagent.tools import ToolAnnotations, ToolRegistry


def _init_repo(root: Path) -> None:
    import subprocess

    subprocess.run(['git', '-C', str(root), 'init'], check=True, capture_output=True)
    subprocess.run(
        ['git', '-C', str(root), 'config', 'user.email', 'test@test.com'],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', '-C', str(root), 'config', 'user.name', 'Test'],
        check=True,
        capture_output=True,
    )


class TestHookRegistry(unittest.TestCase):
    def test_pre_hook_can_veto(self) -> None:
        registry = HookRegistry()
        registry.register_pre_hook(
            lambda tool_name, args: (_ for _ in ()).throw(HookError('blocked'))
        )
        with self.assertRaises(HookError) as ctx:
            registry.run_pre_hooks('test_tool', {})
        self.assertIn('blocked', str(ctx.exception))

    def test_post_hook_receives_result(self) -> None:
        results: list[dict] = []
        registry = HookRegistry()
        registry.register_post_hook(
            lambda tool_name, args, result: results.append(result)
        )
        registry.run_post_hooks('test_tool', {}, {'ok': True})
        self.assertEqual(results, [{'ok': True}])

    def test_disabled_hooks_do_not_fire(self) -> None:
        fired = []
        registry = HookRegistry(
            config=HookConfig(
                pre_hooks=[lambda *a: fired.append('pre')],
                post_hooks=[lambda *a: fired.append('post')],
                enabled=False,
            )
        )
        registry.run_pre_hooks('x', {})
        registry.run_post_hooks('x', {}, {})
        self.assertEqual(fired, [])


class TestHookIntegration(unittest.TestCase):
    def test_pre_hook_veto_blocks_tool_execution(self) -> None:
        registry = HookRegistry()
        registry.register_pre_hook(
            lambda tool_name, args: (_ for _ in ()).throw(HookError('vetoed'))
        )
        tool_reg = ToolRegistry(hook_registry=registry)
        tool_reg.register(
            name='echo',
            description='echo',
            input_schema={'type': 'object', 'properties': {}},
            output_schema={'type': 'object', 'properties': {}},
            annotations=ToolAnnotations(),
            handler=lambda args: {'ok': True},
        )
        with self.assertRaises(HookError) as ctx:
            tool_reg.execute('echo', {})
        self.assertIn('vetoed', str(ctx.exception))

    def test_post_hook_receives_tool_result(self) -> None:
        results: list[dict] = []
        registry = HookRegistry()
        registry.register_post_hook(
            lambda tool_name, args, result: results.append(result)
        )
        tool_reg = ToolRegistry(hook_registry=registry)
        tool_reg.register(
            name='echo',
            description='echo',
            input_schema={'type': 'object', 'properties': {}},
            output_schema={
                'type': 'object',
                'properties': {'value': {'type': 'integer'}},
            },
            annotations=ToolAnnotations(),
            handler=lambda args: {'value': 42},
        )
        result = tool_reg.execute('echo', {})
        self.assertEqual(result, {'value': 42})
        self.assertEqual(results, [{'value': 42}])


class TestBuiltInHooks(unittest.TestCase):
    def test_shell_command_hook_runs_on_matching_tool(self) -> None:
        registry = HookRegistry()
        registry.register_post_hook(
            shell_command_hook('echo hook_ran', on_tools=frozenset({'my_tool'}))
        )
        # Should not raise
        registry.run_post_hooks('my_tool', {}, {})

    def test_shell_command_hook_skips_non_matching_tool(self) -> None:
        registry = HookRegistry()
        registry.register_post_hook(
            shell_command_hook('exit 1', on_tools=frozenset({'my_tool'}))
        )
        # Should not raise because tool name doesn't match
        registry.run_post_hooks('other_tool', {}, {})

    def test_shell_command_hook_fails_on_bad_command(self) -> None:
        registry = HookRegistry()
        registry.register_post_hook(
            shell_command_hook('exit 1', on_tools=frozenset({'my_tool'}))
        )
        with self.assertRaises(HookError):
            registry.run_post_hooks('my_tool', {}, {})


if __name__ == '__main__':
    unittest.main()
