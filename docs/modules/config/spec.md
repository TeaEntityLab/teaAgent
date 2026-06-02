# config — Behavior Specification

## Purpose

`config` resolves runtime configuration deterministically across defaults, user config, workspace config, and environment variables so every run has explicit, inspectable settings.

## Behavior Contract

1. **Resolution order is fixed**: defaults -> `~/.teaagent/config.json` -> `<root>/.teaagent/config.json` -> `TEAAGENT_*` env vars (`teaagent/config_loader.py:3`, `teaagent/config_loader.py:171`).
2. **Known keys only**: only keys declared in `CONFIG_KEYS` participate in merge (`teaagent/config_loader.py:39`); unknown file keys are ignored.
3. **Type coercion is predictable**: list values accept JSON arrays/comma-delimited strings; boolean env values treat `1/true/yes` as true; invalid config JSON falls back to `{}`.
4. **Source attribution is preserved**: each resolved key records its winning layer (`ResolvedConfig.sources`), and `show()` emits `key = value [layer]` lines.
5. **Workspace loader safety**: `load_workspace_config()` reads only `<root>/.teaagent/config.json`; missing file returns `{}`.

## Invariants

- `ConfigResolver.resolve()` returns `ResolvedConfig` where every key in `values` has a corresponding `sources` entry.
- File-read and JSON-parse errors never crash resolution; lower-precedence layers continue.
- `None`-resolved values are omitted from `ResolvedConfig.values`.
- Environment variables always win when present.
