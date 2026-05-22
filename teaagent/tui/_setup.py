from __future__ import annotations

import getpass
from argparse import Namespace
from pathlib import Path
from typing import TYPE_CHECKING

from teaagent.llm import check_llm_configuration
from teaagent.policy import parse_permission_mode
from teaagent.wizard import WizardResult, run_first_session_setup

if TYPE_CHECKING:
    from teaagent.tui import TeaAgentTUI


def workspace_configured(root: Path) -> bool:
    tea_dir = root / '.teaagent'
    return (tea_dir / 'config.json').is_file() or (tea_dir / 'config.toml').is_file()


def apply_setup_result_to_tui(tui: TeaAgentTUI, result: WizardResult) -> None:
    configured = result.configured
    provider = configured.get('provider')
    if isinstance(provider, str) and provider:
        tui.provider = provider
    permission_mode = configured.get('permission_mode')
    if isinstance(permission_mode, str) and permission_mode:
        tui.permission_mode = parse_permission_mode(permission_mode)


def run_tui_setup(
    tui: TeaAgentTUI,
    *,
    write_env: bool = False,
    provider: str | None = None,
    api_key: str | None = None,
) -> bool:
    """Run the shared first-session wizard from the TUI."""

    def _input(prompt: str) -> str:
        if tui.input_fn is not None:
            return tui.input_fn(prompt)
        return input(prompt)

    def _getpass(prompt: str) -> str:
        if tui.input_fn is not None:
            return tui.input_fn(prompt)
        return getpass.getpass(prompt)

    args = Namespace(
        root=str(tui.root),
        provider=provider or tui.provider,
        api_key=api_key,
        permission_mode=tui.permission_mode.value,
        max_iterations=10,
        max_tool_calls=10,
        context_profile='balanced',
        heartbeat=tui.heartbeat_seconds,
        daily_cost_cap_cents=0,
        write_env=write_env,
        model=tui.model,
    )
    result = run_first_session_setup(
        args,
        check_llm=check_llm_configuration,
        input_fn=_input,
        getpass_fn=_getpass,
    )
    apply_setup_result_to_tui(tui, result)
    tui._save_tui_state()
    tui._print_json(result.to_dict())
    if result.ok:
        tui.output_fn(f'setup: ok — try: {result.safe_command}')
        for step in result.next_steps[:3]:
            tui.output_fn(f'  • {step}')
    else:
        tui.output_fn('setup: incomplete — fix warnings above, then retry setup')
    return result.ok
