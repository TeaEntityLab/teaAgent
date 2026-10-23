# Owner experiment samples — 2026-10-23

> **Claim class:** Sample instructions. Not results, not current truth, and not a status change.
> **Owner:** docs
> **Last reviewed:** 2026-10-23
> **What this is not:** No host was configured. No B1 session was booked. No live provider call was made. The veto was not built. The 2026-11-15 ADR-0031 date is unchanged. ADR-0043 stays archived until 2026-12-09.

Do these in order. Stop when a step says to stop. Reply with what you saw, not with a paraphrase of this file.

Pull the commit that contains `teaagent/foreign_hook.py` before sample 1. The other computer needs that file.

## Sample 1 — Install the observe recorder on the other computer

This is observation only. A crash loses one log line. It cannot allow a tool. Do this on the other computer, not on the machine that produced this file. Do not copy a JSON snippet from one machine to another.

1. On the other computer, in a checkout of this repo, use the interpreter that has TeaAgent installed. A bare `python` is wrong: Claude runs the hook in each project's directory and does not activate the checkout virtualenv.

```bash
/path/to/that/venv/bin/python -m teaagent.foreign_hook --print-install
```

2. Stderr is a warning. Stdout is JSON. The command in the JSON is that interpreter's absolute path, shell-quoted, then `-m teaagent.foreign_hook`. `--print-install` runs that command once from an unrelated temporary directory and prints the snippet only if the probe records an event. If stderr says `not printing an install snippet` or `was not recorded`, stop. Do not paste anything.

The shape, with the path replaced, is:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "'/path/to/that/venv/bin/python' -m teaagent.foreign_hook",
            "async": true
          }
        ]
      }
    ]
  }
}
```

3. Paste that JSON into the **user** Claude Code settings (`~/.claude/settings.json`), not into this repository. If that file already has a `hooks` object, merge the `PostToolUse` entry. Do not commit the settings file.

4. Do not put this command on `PreToolUse`. Do not pass `--enforce`. Do not point it at Codex `PreToolUse`. Codex has no documented fail-closed switch for a crashed hook.

5. In some other project directory, use one ordinary tool (a file read is enough). Then look at `.teaagent/foreign-hooks/observe.jsonl` in **that** project. One line should be a `foreign_hook_observed` event. The fields are the event name, tool name, session id, permission mode, byte count, and a SHA-256 of the stdin. `tool_input` and `tool_response` must not be in the line. If the line is missing, or stderr from the hook said `was not recorded`, the install did not record anything. Say so. That does not close F9 by itself. F9 stays open until sessions outside TeaAgent's runner show up in an audit you can read.

## Sample 2 — B1, one watched coding task

B1 is not a mode and not the shadow gate. It is one task you watch: a tool runs, you approve or reject it, you read the run, and you undo. No session is booked. The 2026-11-15 date stays as it is. Use a scratch directory, not the TeaAgent checkout.

A fresh scratch directory has no `.teaagent/config.toml`. On 2026-10-23 the command with no provider, run in that directory, exited 1 before any tool ran. Stderr was exactly:

```text
provider required: run `teaagent setup` or pass provider on the command line
```

That is not `unknown provider`. Choose a real provider, its credential, and its model before the task. Do not use `fake`. `fake` does not check a credential.

`gpt` is the example below. Its credential is `OPENAI_API_KEY`. Its model in this sample is `gpt-4o-mini`, passed on the run so the model is not an unspoken default. For another provider, use that provider's own environment variable and pass that provider's model with `--model`. `teaagent setup --help` lists the provider names. `ollama` and `vllm` already have a local key and talk to localhost. `workers-ai` and `aigateway` also need account and gateway ids. Use one of those only if `teaagent doctor model <provider>` says ok.

| Provider | Credential variable |
| --- | --- |
| `gpt` | `OPENAI_API_KEY` |
| `claude` | `ANTHROPIC_API_KEY` |
| `gemini` | `GEMINI_API_KEY` |
| `openrouter` | `OPENROUTER_API_KEY` |
| `grok` | `XAI_API_KEY` |
| `mistral` | `MISTRAL_API_KEY` |
| `deepseek` | `DEEPSEEK_API_KEY` |
| `opencodezen`, `opencodezen-go` | `OPENCODEZEN_API_KEY` |

Export the key in the shell you will use. Do not paste it into the repo or into your reply.

```bash
export OPENAI_API_KEY='your-key'
mkdir -p /tmp/teaagent-b1-scratch
cd /tmp/teaagent-b1-scratch
git init -b main
printf 'scratch\n' > NOTES.txt
git add NOTES.txt
git commit -m 'scratch'
teaagent setup --provider gpt --permission-mode prompt
teaagent doctor model gpt
```

Stop unless both of these are true: `setup` exits 0, and `doctor model` prints `"ok": true`. With no key, both exit 1 and the message is `gpt requires OPENAI_API_KEY`. Setup still writes `.teaagent/config.toml`, `AGENTS.md`, and `.gitignore`. Commit `AGENTS.md` and `.gitignore` before the run. `.teaagent/` is gitignored, so the key stays out of the commit. If those files are still untracked, the sandbox stops with `Worktree is dirty. Commit or stash changes first, or use --auto-stash`.

```bash
git add .gitignore AGENTS.md
git commit -m 'Add TeaAgent workspace scaffold'
teaagent agent run --model gpt-4o-mini --permission-mode prompt --hitl-approval --git-sandbox \
  "Add one comment line to NOTES.txt that says b1-sample. Do not touch any other file."
```

The provider comes from `.teaagent/config.toml` after setup. To pass it on the command line instead, put the provider name first and the task second: `teaagent agent run gpt --model gpt-4o-mini ... "Add one comment line..."`. Do that only after `doctor model gpt` is ok. Without the setup scaffold, the run leaves an untracked `.teaagent/` directory.

Checked the same day in a fresh scratch repo, with `OPENAI_API_KEY` unset: after setup, the scaffold commit, and the run command above, the sandbox started and the run failed before any tool call. The audit `run_failed` message was `gpt requires OPENAI_API_KEY`. That check is not a finished B1.

While it runs:

- If it asks before a write, answer there. Approving and rejecting are both a finished sample. Write down which you did.
- When it stops, `teaagent runs list` and then `teaagent runs show <run_id>`. You want the run id, whether a tool was approved or rejected, and that the receipt is readable.
- `teaagent undo --preview` shows the restore diff and does not apply it. `teaagent undo` restores the scratch file when the run has an undo journal.

Reply with the run id and whether you approved, rejected, or never got a prompt. Do not paste tool arguments or file contents.

## Sample 3 — EFX live proof, worksheet only

Do not run a GitHub, browser, or other provider call until all six rows below are filled and you say the call is authorized. Providerless tests are not live proof. The procedure is [efx-live-proof-procedure-2026-08-31.md](../plans/efx-live-proof-procedure-2026-08-31.md). The 2026-08-31 example values in that file are a shape, not authorization for today.

Copy this table into your reply and replace every `blank`:

| # | Item | Your value |
| --- | --- | --- |
| 1 | Throwaway target | blank |
| 2 | Credential scope | blank |
| 3 | Exact payload and call budget | blank |
| 4 | Pre-state | blank |
| 5 | How to reverse it | blank |
| 6 | May a process be killed mid-call? | blank |

Leave permission mode at `prompt`. Do not set `allow` or `danger-full-access`. Do not flip `TEAAGENT_H4_*` out of `shadow`. EFX-001 through EFX-003 stay in progress until a later status change that cites a real run.

## Sample 4 — The veto, not built

There is nothing to install for this one. The observe recorder in sample 1 is not a veto. A veto would be a different process: on Claude Code, a synchronous `PreToolUse` command with `onFailure: "block"` and a short timeout, exiting 2 before it imports TeaAgent, and never printing `permissionDecision: "allow"`. Codex has no documented switch for this. Removing the hook from the host settings still fail-opens. The design is [foreign-hook-safer-path-2026-10-23.md](../reviews/foreign-hook-safer-path-2026-10-23.md).

If you want that process built, reply with this sentence filled in:

`Build the fail-closed veto for <Claude Code only, or name the host>. Do not install it on this machine. The timeout I accept is <seconds>.`

Until that sentence exists, do not add a `PreToolUse` hook, and do not treat F10 as fixed.
