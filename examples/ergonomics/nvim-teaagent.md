# Neovim + TeaAgent

Minimal terminal workflow without a plugin:

```vim
" Map leader key to open a TeaAgent terminal panel
nnoremap <leader>ta :terminal teaagent tui<CR>
```

CLI `@` references work in the TUI after `context list`:

```
context list teaagent
ask Review @teaagent/cli/__init__.py for ergonomics gaps
```

For MCP instead of TUI: `teaagent mcp serve --http` and connect your MCP client.
