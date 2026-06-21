# Five-Minute Governance Proof

**Receipts before rhetoric.**

This demo proves TeaAgent's governance thesis — that every agent action leaves
a verifiable, reversible paper trail — end-to-end in under five minutes with no
API key required.

---

## Quick start

```bash
# From the repo root:
bash scripts/five-minute-proof-demo.sh

# Or run the automated acceptance test:
pytest tests/acceptance/test_five_minute_proof_flow.py -v
```

---

## What the demo proves

| Step | Governance claim | How it is proved |
|------|-----------------|-----------------|
| 1 | No write without a plan | `--require-plan` without `--from-plan` → exit 2, file untouched |
| 2 | Every mutation gated by approval | `approval_granted` event captured; denial blocks the write |
| 3 | Agent edits exactly the declared file | `calc.py` flipped from `a - b` to `a + b`; no other files touched |
| 4 | Agent verifies before declaring done | `workspace_run_shell_inspect` call appears before `final` decision |
| 5 | Full audit receipt emitted | `build_run_receipt()` returns all required sections; `Audit log:` path exists on disk |
| 6 | Workspace fully reversible | `agent undo <run_id>` restores the original file; status = `"restored"` |

---

## Demo scenario

The workspace starts with a buggy calculator:

```python
# calc.py (buggy)
def add(a, b):
    return a - b   # ← wrong operator
```

The agent is asked to fix it. Every action — plan validation, approval, write, verify,
final — is recorded in an append-only audit log under `.teaagent/runs/`.

---

## Step-by-step walkthrough

### Step 1 — Plan gate

```
teaagent agent run gpt 'Fix the bug in calc.py' \
  --root /tmp/demo                               \
  --permission-mode prompt                       \
  --require-plan                                 \
  # (no --from-plan supplied)
```

Expected output:
```json
{"status": "error", "message": "Plan-before-write enforcement requires a bound plan. ..."}
```

Exit code `2`. The file is unchanged. The plan gate fires **before** any LLM call.

**What this proves:** The system enforces intent before execution. You cannot
accidentally mutate files by running the agent without first declaring what you
intend to change.

---

### Step 2 — Governed run with plan and approval

```
teaagent agent run gpt 'Fix the bug in calc.py'  \
  --root /tmp/demo                                \
  --permission-mode prompt                        \
  --from-plan .teaagent/plans/fix-calc.md         \
  --require-plan                                  \
  --git-sandbox-auto-stash                        \
  --approve-scoped workspace_write_file:<sha256-of-tool+args>
```

> `--approve-call-id` was removed (G-P2-2): call ids are predictable, so they were
> weaker authority than a payload digest. Pre-approve the exact payload with
> `--approve-scoped TOOL:SHA256` — the digest covers the tool name + arguments and
> is shown in the pending-approval payload.

The plan file declares:
```markdown
## Files likely touched
- `calc.py`
```

The runner validates the plan hash, creates a git sandbox branch, then enters the
agent loop.

**What this proves:** The plan hash is recorded at run start; any drift from the
declared intent is detectable via the hash and scope check.

---

### Step 3 — File edit

The agent issues:
```json
{"type": "tool", "tool_name": "workspace_write_file",
 "arguments": {"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"},
 "call_id": "fix-write"}
```

Because this exact payload (tool name + arguments) was pre-authorised via
`--approve-scoped` (payload digest), the approval gate records `approval_granted`.
The file is written. The undo journal captures the original content.

After this step:
```python
# calc.py (fixed)
def add(a, b):
    return a + b
```

**What this proves:** The approval is recorded in the audit log *before* the write
executes. The audit trail is immutable and append-only.

---

### Step 4 — Verification

The agent issues a read-only shell inspection (using `grep`, which is in the inspect-safe allowlist):
```json
{"type": "tool", "tool_name": "workspace_run_shell_inspect",
 "arguments": {"command": "grep -n 'return a' calc.py"},
 "call_id": "verify-fix"}
```

This does not require an approval (read-only tool). The result is recorded.

**What this proves:** The agent confirms its work before declaring completion.
The receipt will show both the write and the verify tool call.

---

### Step 5 — Evidence receipt

After the run completes, `build_run_receipt()` produces:

```
Run receipt: <run-id>
Status: success
Goal: Fix the bug in calc.py
Provider/model: gpt / ?
Permission mode: prompt
Plan: .teaagent/plans/fix-calc.md
Plan hash: <sha256-prefix>
Cost: 0 cents (unavailable); budget cap: not set
Audit log: /tmp/demo/.teaagent/runs/<run-id>.jsonl
Resume/checkpoint: checkpoint_available
Final result: calc.py fixed: subtraction corrected to addition; verification passed
Tools used (2): workspace_write_file, workspace_run_shell_inspect
Files touched:
  - calc.py
Commands run:
  - [redacted] [exit 0]
Approvals:
  - workspace_write_file: granted
Rollback/undo: available
```

The `Audit log:` line points to a real `.jsonl` file on disk. Every event in
that file is a timestamped, structured record — not prose.

**What this proves:** The receipt is a machine-verifiable summary of what the
agent actually did, not what it claimed it would do.

---

### Step 6 — Undo

```
teaagent agent undo <run-id> --root /tmp/demo
```

Expected output:
```json
{"status": "restored", "method": "git", "run_id": "<run-id>", "branch": "main"}
```

After undo:
```python
# calc.py (restored)
def add(a, b):
    return a - b   # ← original (buggy) state
```

**What this proves:** Every mutating run is reversible. The undo path is recorded
in the receipt (`Rollback/undo: available`) before you ever need it.

---

## Provider note

Both the shell script and the acceptance test use the built-in `fake` provider:

- Shell demo: `FakeLLMAdapter` from `teaagent.llm._fake_adapter` with scripted
  `LLMResponse` objects — no network calls, no API key.
- Acceptance test: `FakeAdapter` from `tests/conftest.py` patched onto
  `teaagent.cli.create_llm_adapter` — standard pattern used across all
  acceptance tests.

To run with a real provider, replace `gpt` with your configured provider and
supply your API key. The governance machinery is identical; only the LLM
responses change.

---

## Files

| File | Purpose |
|------|---------|
| `scripts/five-minute-proof-demo.sh` | Runnable shell demo with narration |
| `docs/demo/five-minute-proof.md` | This walkthrough |
| `tests/acceptance/test_five_minute_proof_flow.py` | Automated acceptance test |

---

## Acceptance criteria (W10)

- [x] Demo runs from clean checkout (`bash scripts/five-minute-proof-demo.sh`)
- [x] Demo output includes evidence bundle path (`Audit log:` line in receipt)
- [x] No dependency on paid live provider (fake provider used throughout)
- [x] Runs locally in under five minutes
- [x] Each step narrated with a clear "what this proves" explanation
