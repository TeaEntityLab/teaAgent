# workspace_tools — Risk Vectors & Known Issues

## R1: Path traversal via symlinks
**File**: `workspace_tools/_helpers.py` — `resolve_workspace_path`
**Risk**: `Path.resolve()` follows symlinks. A symlink inside the workspace pointing outside (e.g., `/etc`) would resolve to a path outside `workspace_root` and be blocked. But if `workspace_root` itself contains a symlink at its root that points outward, the check may pass incorrectly.
**Mitigation**: Ensure `workspace_root` is a real path, not a symlink.

## R2: `workspace_edit_at_hash` race condition
**File**: `workspace_tools/_files.py` — `workspace_edit_at_hash` handler
**Risk**: Between the agent reading a file (computing hash) and calling `workspace_edit_at_hash`, another process may modify the file. The hash check then fails, but the agent has already planned the edit.
**Failure mode**: Edit fails; agent must re-read and retry. No data loss, but confusing UX.

## R3: Shell command injection through arguments
**File**: `workspace_tools/_shell.py` — `run_shell_inspect`
**Risk**: If `workspace_shell` tool passes command arguments directly to `subprocess` with `shell=True`, arbitrary code can execute. Must verify `shell=False` or strict argument parsing.
**Failure mode**: Arbitrary command execution in agent context.
**Mitigation**: Verify `_shell.py` uses `shell=False` and list-form commands.

## R4: Write size limit bypassed by sequential writes
**File**: `workspace_tools/_helpers.py` — `assert_write_size_allowed`
**Risk**: `max_write_bytes` applies per-call. An agent can write 999 files at just-under the limit, accumulating large total writes.
**Failure mode**: Disk exhaustion.

## R5: Knowledge backend failure silently degrades
**File**: `workspace_tools/_files.py:13-17`
**Risk**: `FallbackKnowledgeBackend` chains backends and returns empty results if all fail. An agent may get empty search results and hallucinate answers.
**Failure mode**: Incorrect code edits based on stale/absent knowledge.

## R6: gitignore matching is approximate
**File**: `workspace_tools/_config.py` — `_load_gitignore_matcher`
**Risk**: Custom gitignore parser may not perfectly match git's behavior (nested .gitignore files, negation patterns). Sensitive files in gitignored dirs may appear in listings.
