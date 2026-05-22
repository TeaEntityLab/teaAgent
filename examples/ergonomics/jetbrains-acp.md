# JetBrains + TeaAgent (ACP)

1. Run `teaagent init` in the repository root.
2. Point the JetBrains ACP plugin at the TeaAgent stdio server (`run_acp_server` transport).
3. Send tasks with `contextBlocks` (selection, diff, file) — merged via `prompt/assemble`.
4. Resume paused runs: `teaagent agent attach <run_id> --resume`.
