#!/usr/bin/env bash
# Build a TeaAgent WASM skill directory (Rust wasm32-wasi when Cargo.toml exists).
set -euo pipefail

SKILL_PATH="${1:-}"
TARGET="${WASM_TARGET:-wasm32-wasi}"

if [[ -z "${SKILL_PATH}" ]]; then
  echo "Usage: $0 <skill-directory>" >&2
  exit 1
fi

cd "${SKILL_PATH}"
if [[ -f Cargo.toml ]]; then
  rustup target add "${TARGET}" 2>/dev/null || true
  cargo build --release --target "${TARGET}"
  mkdir -p dist
  find "target/${TARGET}/release" -maxdepth 1 -name '*.wasm' -exec cp {} dist/tool.wasm \;
fi

cd - >/dev/null
teaagent sandbox wasm-contract "${SKILL_PATH}" --write-manifest --validate
echo "WASM skill ready under ${SKILL_PATH}"
