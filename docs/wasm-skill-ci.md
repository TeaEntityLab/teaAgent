# WASM skill CI templates

TeaAgent ships a **reusable GitHub Actions workflow** for building and validating WASM skill modules.

## Workflow

File: [`.github/workflows/wasm-skill-build.yml`](../.github/workflows/wasm-skill-build.yml)

Caller example:

```yaml
jobs:
  build-my-skill:
    uses: TeaEntityLab/teaAgent/.github/workflows/wasm-skill-build.yml@main
    with:
      skill_path: skills/example
```

Steps performed:

1. Install Rust `wasm32-wasi` (configurable via `rust_target` input).
2. `cargo build --release` when `Cargo.toml` exists under `skill_path`.
3. `teaagent sandbox wasm-contract --write-manifest --validate`.
4. Upload `dist/`, `*.wasm`, and `wasm_manifest.json` as an artifact.

## Local script

[`scripts/build_wasm_skill.sh`](../scripts/build_wasm_skill.sh) mirrors the compile + manifest steps for local dev.

## Contract

See [`teaagent/wasm_skill.py`](../teaagent/wasm_skill.py) and `teaagent sandbox wasm-contract`.
