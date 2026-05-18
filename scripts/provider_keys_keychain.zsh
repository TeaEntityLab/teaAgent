#!/usr/bin/env zsh
# TeaAgent provider key bootstrap using macOS Keychain.
#
# Usage:
#   source ~/.teaagent/provider_keys_keychain.zsh
#   teaagent_configure_provider_keys
#
# Keys are stored under service names: teaagent/<ENV_VAR>

_teaagent_load_key_from_keychain() {
  local var_name="$1"
  if [[ -n "${(P)var_name}" ]]; then
    return 0
  fi

  local keychain_service="teaagent/${var_name}"
  local key_value
  key_value="$(security find-generic-password -a "$USER" -s "$keychain_service" -w 2>/dev/null)" || return 0
  export "${var_name}=${key_value}"
}

_teaagent_set_key_in_keychain() {
  local var_name="$1"
  local keychain_service="teaagent/${var_name}"
  local key_value

  read -r -s "?Enter ${var_name}: " key_value
  echo
  if [[ -z "$key_value" ]]; then
    echo "Skipped ${var_name} (empty input)"
    return 0
  fi

  security add-generic-password -U -a "$USER" -s "$keychain_service" -w "$key_value" >/dev/null
  export "${var_name}=${key_value}"
  echo "Saved ${var_name} to macOS Keychain (${keychain_service})"
}

teaagent_configure_provider_keys() {
  local vars=(
    ANTHROPIC_API_KEY
    OPENAI_API_KEY
    GEMINI_API_KEY
    OPENROUTER_API_KEY
    OPENCODEZEN_API_KEY
    MISTRAL_API_KEY
    DEEPSEEK_API_KEY
    XAI_API_KEY
    CLOUDFLARE_API_TOKEN
  )
  local v
  for v in "${vars[@]}"; do
    _teaagent_set_key_in_keychain "$v"
  done
}

_teaagent_provider_vars=(
  ANTHROPIC_API_KEY
  OPENAI_API_KEY
  GEMINI_API_KEY
  OPENROUTER_API_KEY
  OPENCODEZEN_API_KEY
  MISTRAL_API_KEY
  DEEPSEEK_API_KEY
  XAI_API_KEY
  CLOUDFLARE_API_TOKEN
)

for _teaagent_provider_var in "${_teaagent_provider_vars[@]}"; do
  _teaagent_load_key_from_keychain "$_teaagent_provider_var"
done

unset _teaagent_provider_var
