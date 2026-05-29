# WASM skill template

Copy this directory into your skill repository and wire CI:

```yaml
jobs:
  wasm:
    uses: TeaEntityLab/teaAgent/.github/workflows/wasm-skill-build.yml@main
    with:
      skill_path: templates/wasm-skill/skill
```

Local build:

```bash
./scripts/build_wasm_skill.sh path/to/skill
```

The skill directory should contain either:

- `Cargo.toml` + Rust sources compiled to `dist/tool.wasm`, or
- A prebuilt `tool.wasm` / `skill.wasm` plus `wasm_manifest.json` from `teaagent sandbox wasm-contract --write-manifest`.
