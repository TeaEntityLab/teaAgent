# Shell Command Execution Safety Audit (SEC-002)

> **Audit date:** 2026-06-07
> **Scope:** All `subprocess.run`, `subprocess.Popen`, `os.system` calls in
> `teaagent/workspace_tools/`, `teaagent/sandbox/`, `teaagent/runner/_core.py`
> **Result:** ✅ **PASS** — No `shell=True` or unsafe string concatenation found.

---

## Summary

| Metric | Count |
|--------|-------|
| Total `subprocess.run` calls audited | 49 |
| `subprocess.Popen` / `os.system` calls | 0 |
| `shell=True` violations | 0 |
| Unsafe string concatenation | 0 |
| Required fixes | 0 |

All subprocess invocations use the **list-argument form** with `shell=False`
(unset/default), which prevents shell injection even when user-provided strings
are passed as individual list elements.

---

## Files Audited

### `teaagent/workspace_tools/_shell.py` — 2 calls

| Line | Pattern | User input? | Safe? |
|------|---------|-------------|-------|
| 68 | `subprocess.run(argv, ..., shell=False)` | Yes — `argv` from `shlex.split(command)` | ✅ Safe |
| 122 | `subprocess.run(argv, ..., shell=False)` | Yes — `argv: list[str]` parameter | ✅ Safe |

**Details:** The primary shell tool entry point (`run_shell`) parses agent-provided
command strings with `shlex.split()`, producing a POSIX-compliant argument list.
This list is then passed directly to `subprocess.run(argv)` with `shell=False`.
The command is also validated by `assert_shell_command_size_allowed()`,
`classify_shell_command_policy()`, and `_has_unquoted_shell_operator()` before execution.

**Environment:** Both functions construct the environment dict via an allowlist
of `SAFE_ENV_PATTERNS`, filtering out secrets/tokens by name. Pagers are forced
to `cat` to prevent interactive hijacking.

### `teaagent/workspace_tools/_git.py` — 1 call

| Line | Pattern | User input? | Safe? |
|------|---------|-------------|-------|
| 22 | `subprocess.run(['git', '-C', str(config.root)] + args, ...)` | Yes — `args` from list operations | ✅ Safe |

**Details:** All callers (`git_add`, `git_commit`, `git_create_branch`, etc.)
construct `args` as Python lists using `.append()`, `.extend()`, or list literals.
User-provided strings (`message`, `name`, `target`, `pathspec`) are appended as
individual list elements. No string concatenation or `shell=True`.

### `teaagent/workspace_tools/_files.py` — 1 call

| Line | Pattern | User input? | Safe? |
|------|---------|-------------|-------|
| 719 | `subprocess.run(['git', 'status', '--short'], ...)` | No — hardcoded | ✅ Safe |

**Details:** Fully hardcoded argument list. No user input reaches the command.

### `teaagent/sandbox/_os_sandbox.py` — 1 call

| Line | Pattern | User input? | Safe? |
|------|---------|-------------|-------|
| 123 | `subprocess.run(command, ...)` | Yes — `command: list[str]` parameter | ✅ Safe |

**Details:** `execute_sandboxed()` takes `command: list[str]` as input. The caller
is responsible for providing a pre-split list. The sandbox validates `cwd` is
within allowed paths and sanitizes the environment (removes secrets, restricts PATH).

### `teaagent/sandbox/_parallel_experiment.py` — 8 calls

| Line | Command | User input? | Safe? |
|------|---------|-------------|-------|
| 70 | `['git', 'rev-parse', '--abbrev-ref', 'HEAD']` | No | ✅ Safe |
| 120 | `['git', 'diff', '--stat', branch, branch]` | Internal strings | ✅ Safe |
| 190 | `['git', 'checkout', branch]` | Internal strings | ✅ Safe |
| 221 | `['git', 'branch', '-D', branch]` | Internal strings | ✅ Safe |
| 267 | `['git', 'checkout', branch]` | Internal strings | ✅ Safe |
| 278 | `['git', 'checkout', branch]` | Internal strings | ✅ Safe |
| 289 | `test_command` (param `list[str]`) | ⚠️ External list | ✅ Safe (list form) |
| 343 | `['git', 'checkout', branch]` | Internal strings | ✅ Safe |

**Details:** Line 289 passes `test_command: list[str]` directly from the caller.
While the list contents are caller-controlled, the list-form argument with no
`shell=True` prevents injection. Callers should ensure list elements are safe.

### `teaagent/sandbox/_git_branch.py` — 36 calls

All 36 subprocess calls use hardcoded git command lists with parameters passed
as individual list elements. No `shell=True`. Representative examples:

| Line | Pattern | Safe? |
|------|---------|-------|
| 34 | `['git', 'rev-parse', '--is-inside-work-tree']` | ✅ Safe |
| 68 | `['git', 'stash', 'push', '-u', '-m', label]` | ✅ Safe |
| 166 | `['git', 'rev-parse', '--abbrev-ref', 'HEAD']` | ✅ Safe |
| 837 | `['git', 'show', ':1:' + file_path]` | ✅ Safe (*) |
| 1038 | `['ruff', 'check', str(full_path)]` | ✅ Safe |
| 1052 | `['mypy', str(full_path)]` | ✅ Safe |

(*) Line 837 uses `':1:' + file_path` — a git index-stage path constructed from
git-produced file names, not arbitrary user input.

### `teaagent/runner/_core.py` — 0 calls

No subprocess or os.system calls found.

---

## Edge Cases & Non-Risks

### 1. `stash_save` — `--grep={label}` pattern (low risk)
`_git_branch.py` line 83 passes `f'--grep={label}'` as a git stash argument.
The `label` is an internally-constructed stash label string. Since it's a list
element (not interpolated into a shell string), shell injection is impossible.
Git's `--grep` accepts regex; injection here would only affect git's stash list
filtering, not system commands.

### 2. `run_tests` — user-provided `test_command` (design note)
`_parallel_experiment.py` line 289 takes `test_command: list[str]`. The type
annotation signals the caller must provide a pre-split list. No shell parsing
happens. This is the only call site where external strings reach `subprocess.run`
without internal mediation. Review callers of `run_tests()` to ensure they
construct the list safely.

### 3. GPG signing in `audit_verify_command` (secondary concern)
`_audit.py` lines 182-194 invoke `gpg --detach-sign` with user-provided key path.
Uses list form. Not part of the shell tool path but noted for completeness.

---

## Verified Safe Sites

The following sites have been verified and annotated with `# shellcheck: arguments`
comments:

| File | Lines | Pattern |
|------|-------|---------|
| `workspace_tools/_shell.py` | 68-76 | `shlex.split` + list form + `shell=False` |
| `workspace_tools/_shell.py` | 122-130 | List parameter + `shell=False` |
| `workspace_tools/_git.py` | 22-28 | List concatenation, no `shell=True` |
| `workspace_tools/_files.py` | 719-725 | Hardcoded list |
| `sandbox/_os_sandbox.py` | 123-130 | List parameter |
| `sandbox/_parallel_experiment.py` | 70-76, 120-132, 289-295 | List form throughout |
| `sandbox/_git_branch.py` | Multiple | All list form |

---

## Recommendations

1. **NO changes needed** — all subprocess calls are safe as-is.
2. Consider adding a `shlex.split()` call in `_parallel_experiment.py:run_tests()`
   if callers ever pass a single string instead of a pre-split list (belt-and-suspenders).
3. Add a pre-commit hook or CI check that scans for `shell=True` and rejects it
   (with an explicit allowlist for documented exceptions).
4. Continue requiring `list[str]` typing for all command parameters as a
   type-level safety guarantee.
