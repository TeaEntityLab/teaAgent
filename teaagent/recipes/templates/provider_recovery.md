# Provider Recovery Recipe

**When to use:** Your LLM provider key is missing, expired, or returning errors.
TeaAgent shows `teaagent doctor model <provider>` failing or the model returns
empty responses with no content.

## Step 1: Diagnose the provider

Run the doctor check to see what is wrong:

```bash
teaagent doctor model <provider>
```

Replace `<provider>` with your provider name: `gpt`, `claude`, `gemini`,
`opencodezen-go`, `deepseek`, `mistral`, `grok`, `ollama`, `vllm`,
`workers-ai`, `aigateway`.

## Step 2: Set a valid API key

Export the correct key for your provider:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export GEMINI_API_KEY="..."
export OPENCODEZEN_API_KEY="..."
export DEEPSEEK_API_KEY="sk-..."
export MISTRAL_API_KEY="..."
export XAI_API_KEY="..."
```

Or use the interactive wizard to prompt for a key:

```bash
teaagent setup --root . --provider <provider> --write-env
```

## Step 3: Verify the key is detected

```bash
teaagent doctor model <provider>
```

Expected output: `ok: true` and a `message` confirming the provider responds.

## Step 4: Restore daily readiness

```bash
teaagent daily "readiness" --dry-run --human --root .
```

**Persistent setup (recommended):** Copy `scripts/providers_env.zsh` to
`~/.teaagent/providers_env.zsh`, fill in your keys, then source it from
`~/.zshrc`. Run `teaagent setup --root . --write-env` for per-project overrides.
