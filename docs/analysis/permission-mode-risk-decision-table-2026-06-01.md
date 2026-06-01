# Permission-Mode Risk Decision Table
# 2026-06-01

**Fills:** Gap **F-ECO-013** — *"add a risk-mode decision table and verify docs mention
the same constraints for CLI, TUI, automation, MCP, cloud, and gateway paths."*
Security facts are currently spread across the threat model, product contract, maturity
matrix, and several risk audits. A user choosing how to run teaagent needs **one table**
that answers: *"What risk am I accepting in this mode?"*

**Grounding.** The five modes are the real `PermissionMode` enum
(`teaagent/approval_manager.py:31`):
`READ_ONLY='read-only'`, `WORKSPACE_WRITE='workspace-write'`, `PROMPT='prompt'`,
`ALLOW='allow'`, `DANGER_FULL_ACCESS='danger-full-access'`. Enforcement is
`PermissionModeEnforcer` (`approval_manager.py:144`); approval handling is grounded in
`tui/__init__.py::_approval_handler` and the preset store.

---

## The decision table

| Mode | Writes? | Destructive tools? | Prompts operator? | Blast radius | Accept this when… | Do NOT use when… |
|------|:------:|:------------------:|:-----------------:|--------------|-------------------|------------------|
| **read-only** | ✗ | ✗ | n/a | None — analysis only | Inspecting/planning, untrusted repo, demoing, CI dry-run | You need the agent to actually change files |
| **workspace-write** | ✓ (in root) | ✗ | ✗ for safe writes | Files under workspace root; no destructive ops | Trusted local repo with git backup; iterative coding | No git safety net; shared/production checkout |
| **prompt** *(default)* | ✓ | ✓ *with approval* | ✓ each destructive call | Whatever you approve, per call | Default daily driver; you want a human gate on each risky step | Unattended/background runs (you won't be there to approve) |
| **allow** | ✓ | ✓ *without prompt* | ✗ | Anything the toolset permits, no gate | Throwaway sandbox/container; you accept full auto | Any environment with data you can't lose |
| **danger-full-access** | ✓ | ✓ | ✗ | **Unbounded** — including outside workspace | Disposable VM/CI only, explicitly understood | Ever, on a machine with real data or credentials |

**Default is `prompt`** (`PermissionMode.PROMPT` is the TUI default), which matches the
survey's strongest signal: trust requires every action to be visible, attributed, and
gated (UX-F2/UX-F7).

---

## Surface × mode constraints (the F-ECO-013 consistency check)

Each surface must enforce the *same* mode semantics. Current state:

| Surface | Honors mode? | Caveat to document |
|---------|:------------:|--------------------|
| CLI `agent run` | ✓ | — |
| TUI / `teaagent chat` | ✓ | `_approval_handler` offers y/n/path/tool/stop; preset grants persist 8h |
| Automation / background | ✓ | `prompt` is unusable unattended → must pre-grant or use JIT approval server; **document this** |
| MCP (remote) | ⚠ | Remote MCP tools cross a trust boundary; mode alone is insufficient — pair with MCP trust review (F-ECO-008) |
| Cloud / managed runtime | ⚠ | Same as background + tenant isolation; verify mode is not silently widened |
| Gateway (Slack/etc.) | ⚠ | Task intake from a message must not escalate mode; default to `prompt` or `read-only` |

**Required doc action:** the threat model, product contract, and `docs/USAGE.md` must
all state these same six rows. F-ECO-013 is only closed when a doc-lint asserts the
constraint text matches across them.

---

## Interactions with known findings

- **`prompt` + background = trap.** A `prompt`-mode run detached to background
  (`/background`, `agent run --detach`) has no operator to answer prompts. Document the
  required path (pre-grant presets or JIT approval), or refuse the combination.
- **`allow`/`danger-full-access` + broken undo (CG-02).** In high-autonomy modes the
  destructive-undo bug is maximally dangerous: no per-call gate *and* an undo that wipes
  the worktree. Until P0-2 lands, high-autonomy modes carry the PR-1 data-loss risk at
  full force — note this in the mode docs.
- **Mode is not visible in the evidence bundle until added.** The run-evidence spec adds
  `identity.permission_mode` so a reviewer can confirm *how governed* a run was.

---

## Acceptance

- `test_mode_capabilities`: parametrized over all five modes — assert writes/destructive/
  prompt behavior matches this table.
- `test_mode_consistency_docs`: doc-lint that threat-model, product-contract, and USAGE
  describe identical constraints per surface.
- `test_prompt_mode_background_guard`: detaching a `prompt`-mode run either pre-requires
  grants or fails with a clear message (no silent hang).

## One-line guidance for the README

> Start in `prompt` (default). Drop to `read-only` for untrusted code. Only use
> `allow`/`danger-full-access` in a disposable sandbox you can throw away.
</content>
