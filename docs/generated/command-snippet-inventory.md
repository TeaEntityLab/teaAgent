# Command Snippet Inventory (Generated)

> **Not current truth.** Coverage labels come from [command-snippet-registry.md](../governance/command-snippet-registry.md).

**Snippets found:** 56

Regenerate: `python3 scripts/generate_command_snippet_inventory.py`

| Command | Source | Coverage | Verification |
| --- | --- | --- | --- |
| `teaagent --config .teaagent/config.json model smoke gpt` | `docs/cli.md:31` (0de72469) | manual | Alternate config path smoke |
| `teaagent --help` | `docs/cli.md:25` (d09b09bd) | manual | CLI help smoke |
| `teaagent agent daily gpt "Summarize the tests" --permission-mode read-only` | `README.md:364` (05bc391c) | smoke | tests/acceptance/test_daily_cli.py |
| `teaagent agent daily gpt "map subsystem boundaries" --context-profile deep` | `docs/USAGE.md:372` (3ac367a2) | smoke | tests/acceptance/test_daily_cli.py |
| `teaagent agent daily gpt "plan test fix" --context-profile balanced` | `docs/USAGE.md:371` (291ea4fe) | smoke | tests/acceptance/test_daily_cli.py |
| `teaagent agent daily gpt "review auth flow" --context-profile lean` | `docs/USAGE.md:370` (efe69395) | smoke | tests/acceptance/test_daily_cli.py |
| `teaagent agent daily gpt "what I want to do today" --permission-mode read-only --root .` | `docs/USAGE.md:331` (41b8128d) | smoke | tests/acceptance/test_daily_cli.py |
| `teaagent agent preflight gpt "fix tests/test_foo.py" --route-model` | `docs/USAGE.md:373` (d6336bc5) | manual | Preflight smoke with configured provider |
| `teaagent agent run gpt "Analyze this codebase" --permission-mode read-only` | `README.md:333` (a8e6903c) | manual | Agent run smoke with configured provider |
| `teaagent agent run gpt "Improve this project" --clarify` | `README.md:358` (d2ccc65c) | manual | Agent run smoke with configured provider |
| `teaagent agent run gpt "Inspect this repo and summarize the test suite"` | `README.md:352` (528345e2) | manual | Agent run smoke with configured provider |
| `teaagent agent run gpt "Update README" --permission-mode workspace-write --route-model` | `README.md:355` (5ef6ae13) | manual | Agent run smoke with configured provider |
| `teaagent agent run gpt "fix tests/test_foo.py" --permission-mode workspace-write` | `docs/USAGE.md:374` (76f03456) | manual | Agent run smoke with configured provider |
| `teaagent agent run gpt "inspect src/app.py" --code-analysis` | `README.md:375` (153bc54d) | manual | Agent run smoke with configured provider |
| `teaagent agent runs` | `README.md:361` (0493189b) | manual | Run list smoke |
| `teaagent agent undo --last --root .` | `docs/USAGE.md:34` (6dc512e7) | manual | Undo smoke after mutating run |
| `teaagent approval check workspace_write_file --path src/foo.py --root .` | `docs/USAGE.md:67` (a85952bb) | manual | Scoped grant check smoke |
| `teaagent approval grant workspace_run_shell_mutate --command-prefix 'pytest ' --root .` | `docs/USAGE.md:65` (f0759ae5) | manual | Scoped grant smoke in prompt mode |
| `teaagent approval grant workspace_write_file --path-glob 'src/**' --root .` | `docs/USAGE.md:64` (d23e51ed) | manual | Scoped grant smoke in prompt mode |
| `teaagent approval list --root .` | `docs/USAGE.md:66` (a70466b0) | smoke | tests/test_cli_ergonomics_handlers.py |
| `teaagent approval subagents list` | `docs/USAGE.md:69` (110fecba) | manual | Subagent queue smoke when enabled |
| `teaagent chat` | `docs/USAGE.md:53` (ddc26048) | manual | Operator REPL smoke before release |
| `teaagent daily "readiness" --dry-run --human --root .` | `docs/USAGE.md:122` (115d08b7) | smoke | tests/test_cli_ergonomics_handlers.py |
| `teaagent daily "readiness" --dry-run --human --root /tmp/teaagent-try` | `docs/USAGE.md:129` (e0938d05) | smoke | tests/test_cli_ergonomics_handlers.py |
| `teaagent daily "summarize this repo" --dry-run --root . --human` | `README.md:46` (089a153a) | smoke | tests/test_cli_ergonomics_handlers.py |
| `teaagent daily "what I want to do today" --human` | `README.md:59` (2eb1b8cb) | smoke | tests/test_cli_ergonomics_handlers.py |
| `teaagent doctor aigateway` | `docs/USAGE.md:283` (5d4fb3df) | manual | AI gateway doctor smoke |
| `teaagent doctor mcp --wizard --root .` | `docs/USAGE.md:135` (59681397) | manual | MCP wizard smoke when MCP enabled |
| `teaagent doctor model claude` | `docs/USAGE.md:275` (97c53b40) | manual | Provider-dependent local smoke |
| `teaagent doctor model gpt` | `docs/USAGE.md:109` (a3e56c73) | manual | Provider-dependent local smoke |
| `teaagent doctor model gpt --wizard` | `docs/USAGE.md:281` (52f07f7e) | manual | Provider-dependent local smoke |
| `teaagent doctor model ollama` | `docs/USAGE.md:276` (ad4c3d52) | manual | Provider-dependent local smoke |
| `teaagent doctor model opencodezen` | `docs/USAGE.md:278` (35841458) | manual | Provider-dependent local smoke |
| `teaagent doctor model opencodezen-go` | `docs/USAGE.md:279` (58759ddc) | manual | Provider-dependent local smoke |
| `teaagent doctor model vllm` | `docs/USAGE.md:277` (ecad996b) | manual | Provider-dependent local smoke |
| `teaagent doctor model workers-ai` | `docs/USAGE.md:280` (b502e22e) | manual | Provider-dependent local smoke |
| `teaagent doctor project --wizard --root .` | `docs/USAGE.md:287` (dd834a3f) | manual | Project doctor wizard smoke |
| `teaagent doctor providers --wizard` | `docs/USAGE.md:285` (2da4c979) | manual | Provider-dependent local smoke |
| `teaagent doctor providers --wizard --provider gpt --provider workers-ai --write-env --root .` | `docs/USAGE.md:286` (1cc7d1bf) | manual | Provider-dependent local smoke |
| `teaagent mcp serve --http --port 7330 --root .` | `docs/USAGE.md:136` (bba97100) | manual | MCP server smoke when MCP enabled |
| `teaagent memory failures` | `docs/USAGE.md:75` (757e3dcc) | manual | Operator memory hygiene smoke |
| `teaagent memory failures auto-invalidate` | `docs/USAGE.md:76` (8a34f85c) | manual | Operator memory hygiene smoke |
| `teaagent memory failures prune` | `docs/USAGE.md:77` (2fc86c80) | manual | Operator memory hygiene smoke |
| `teaagent model smoke gpt --prompt "Reply with exactly: ok"` | `docs/USAGE.md:294` (39e44d39) | manual | Provider smoke with configured credentials |
| `teaagent plan gpt "summarize the test suite" --root . --permission-mode read-only` | `docs/USAGE.md:26` (fab3e1b5) | manual | Operator plan artifact smoke before release |
| `teaagent run "summarize the test suite" --permission-mode read-only` | `README.md:60` (1a2f1708) | manual | Operator golden-path smoke before release |
| `teaagent run "summarize the test suite" --permission-mode read-only --root .` | `README.md:49` (cc26544c) | manual | Operator golden-path smoke before release |
| `teaagent run gpt "fix the failing auth tests" --permission-mode workspace-write --from-plan .teaagent/plans/fix-auth-tests.md --root .` | `docs/USAGE.md:30` (563c18ea) | manual | Operator golden-path smoke before release |
| `teaagent run gpt "quick fix" --permission-mode workspace-write --skip-plan-check --root .` | `docs/USAGE.md:32` (10b8ddbf) | manual | Operator golden-path smoke before release |
| `teaagent run gpt --from-plan .teaagent/plans/20260526-120000-summarize-the-test-suite.md --permission-mode read-only --root .` | `docs/USAGE.md:28` (7a4e84b3) | manual | Operator golden-path smoke before release |
| `teaagent setup --root . --permission-mode read-only` | `docs/USAGE.md:115` (2f5fc58d) | smoke | tests/acceptance/test_daily_cli.py |
| `teaagent setup --root . --provider gpt --permission-mode read-only --write-env` | `README.md:43` (96100884) | smoke | tests/acceptance/test_daily_cli.py |
| `teaagent setup --root . --provider gpt --write-env` | `docs/USAGE.md:108` (a1a8f273) | smoke | tests/acceptance/test_daily_cli.py |
| `teaagent setup --root /tmp/teaagent-try --provider gpt --api-key "$OPENAI_API_KEY"` | `docs/USAGE.md:128` (f19c7372) | smoke | tests/acceptance/test_daily_cli.py |
| `teaagent tui --root . --permission-mode prompt` | `docs/USAGE.md:391` (a8e4a35a) | manual | Operator TUI smoke before release |
| `teaagent tui --setup --root .` | `docs/USAGE.md:43` (784651ba) | manual | Operator TUI smoke before release |
