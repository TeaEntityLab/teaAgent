#!/usr/bin/env zsh
# TeaAgent Provider API Key Setup
# Source this file to set all provider API keys at once.
#
# Usage:
#   1. Copy this file: cp scripts/provider_keys.zsh ~/.teaagent/provider_keys.zsh
#   2. Edit it to fill in your keys
#   3. Add to your ~/.zshrc:
#        source ~/.teaagent/provider_keys.zsh
#   4. Or load manually:
#        source ~/.teaagent/provider_keys.zsh

# --- Anthropic (Claude) ---
# Get your key at: https://console.anthropic.com/settings/keys
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"

# --- OpenAI (GPT) ---
# Get your key at: https://platform.openai.com/api-keys
export OPENAI_API_KEY="${OPENAI_API_KEY:-}"

# --- Google Gemini ---
# Get your key at: https://aistudio.google.com/apikey
export GEMINI_API_KEY="${GEMINI_API_KEY:-}"

# --- OpenRouter ---
# Get your key at: https://openrouter.ai/settings/keys
export OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"

# --- OpenCodeZen ---
# Get your key at: https://opencode.ai/settings
export OPENCODEZEN_API_KEY="${OPENCODEZEN_API_KEY:-}"

# --- Optional: Custom base URLs (uncomment to override) ---
# export ANTHROPIC_BASE_URL="https://api.anthropic.com/v1"
# export OPENAI_BASE_URL="https://api.openai.com/v1"
# export GEMINI_BASE_URL="https://generativelanguage.googleapis.com/v1beta"
# export OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"
# export OPENCODEZEN_BASE_URL="https://opencode.ai/zen/go/v1"

# --- Provider-specific model overrides ---
# Uncomment and edit to override the default model for a provider:
# export CLAUDE_MODEL="claude-3-5-sonnet-latest"
# export GPT_MODEL="gpt-4o-mini"
# export GEMINI_MODEL="gemini-1.5-flash"
# export OPENROUTER_MODEL="openai/gpt-4o-mini"
# export OPENCODEZEN_GO_MODEL="deepseek-v4-flash"

# --- Quick verification ---
# Run after sourcing: teaagent doctor model <provider>