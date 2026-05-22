# Zed + TeaAgent (ACP)

1. Install TeaAgent in the project: `teaagent init --root . --provider gpt`.
2. Configure Zed Agent Client Protocol to launch:
   `teaagent mcp serve` or your ACP bridge that forwards `prompt/assemble`.
3. Use `prompt/assemble` with `contextBlocks` for editor selection and open buffers.
4. Daily ritual: `teaagent daily "plan"` then `teaagent run "task" --dry-run`.

See [docs/cli.md](../../docs/cli.md) for providerless shortcuts after init.
