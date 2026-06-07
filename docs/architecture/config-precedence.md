# Configuration Precedence (ARC-008)

TeaAgent resolves runtime configuration from multiple layers. **Higher layers override lower layers.**

| Priority | Source | Example |
|----------|--------|---------|
| 1 (highest) | CLI flags | `--provider claude`, `--permission-mode prompt` |
| 2 | `--config` file / profile | `.teaagent/config.json`, `profiles.dev` |
| 3 | Workspace defaults | `.teaagent/config.json` without explicit CLI |
| 4 | Environment variables | `ANTHROPIC_API_KEY`, `TEAAGENT_*` |
| 5 | User-level env file | `~/.teaagent/providers_env.zsh` |
| 6 (lowest) | Built-in defaults | `ConfigResolver` fallbacks |

## Canonical access

- Use `ConfigResolver.resolve()` from `teaagent.config_loader` for merged config.
- Use `ProviderConfig.resolved_api_key()` for provider credentials.
- Avoid new direct `os.environ.get()` calls outside the allowlist in `scripts/audit_config_access.py`.

## Validation commands

```bash
teaagent doctor config-lint
teaagent setup --verify
python3 scripts/audit_config_access.py
```

## Caching

`ConfigResolver` caches parsed config keyed by source file mtime (PERF-005). Call `clear_config_cache()` in tests that mutate config files.
