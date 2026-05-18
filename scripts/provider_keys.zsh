#!/usr/bin/env zsh
# Backward-compatible alias for older docs/scripts.
# Preferred template: scripts/providers_env.zsh
#
# If you previously sourced ~/.teaagent/provider_keys.zsh, keep it and update
# its content to source ~/.teaagent/providers_env.zsh.

script_path="${(%):-%x}"
script_dir="${script_path:A:h}"

if [[ -f "${script_dir}/providers_env.zsh" ]]; then
  # shellcheck source=/dev/null
  source "${script_dir}/providers_env.zsh"
else
  echo "provider_keys.zsh fallback failed: providers_env.zsh not found" >&2
  return 1 2>/dev/null || exit 1
fi
