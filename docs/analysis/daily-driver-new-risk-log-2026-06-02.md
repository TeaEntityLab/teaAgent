# Daily-Driver New Risk Log
# 2026-06-02

This risk log captures a fresh read-only review pass focused on daily stability,
evidence integrity, and operator trust.

## RL-NEW-01: Dry-run and read-only preflight side effects

**Type:** Risk / verification

Commands described as dry-run or read-only can still initialize project state when they
call preflight, daily brief, memory, or run-store helpers that create `.teaagent`
directories.

**Why it matters:** A user who asks for a read-only check should not see hidden
workspace writes unless first-run initialization is explicitly part of the contract.

**Recommended capture:** Add a daily-driver invariant: dry-run/read-only commands do
not create `.teaagent`, journals, run directories, or memory files unless the command
prints that it will initialize local state.

**Verification:** Run the command in a fresh temp workspace and compare filesystem
snapshots before/after.

## RL-NEW-02: Context-pack read-only truth label

**Type:** Defeat / evidence integrity

`build_context_pack(..., readonly=False)` can return a `ContextPack` whose serialized
`read_only` field is still `true`, because the dataclass default is not overridden.

**Why it matters:** Evidence bundles must not blur "this is a read-only evidence type"
with "this call had no side effects."

**Recommended capture:** Either pass the caller's `readonly` argument through or rename
the field to describe the artifact instead of side-effect behavior.

**Verification:** Unit test `build_context_pack(readonly=False).to_dict()['read_only']`
or the renamed replacement.

## RL-NEW-03: Pinned-file containment

**Type:** Security / stability

Pinned-file storage treats the requested file as `root / file_path` and checks existence,
but does not clearly reject absolute paths, parent traversal, or symlink escape.

**Why it matters:** Live-context pinning should not become a path escape hatch.

**Recommended capture:** Require workspace-relative paths, resolve them, and verify
containment under the workspace root before reading or storing.

**Verification:** Add tests for absolute path, `../`, symlink escape, missing file, and
allowed relative file.

## RL-NEW-04: Silent corrupt state loss

**Type:** Defeat / verification

Memory and run-store readers can skip corrupt JSON lines or return `None` for corrupt
run files. Daily surfaces can then look clean while state is actually degraded.

**Why it matters:** Daily cockpit trust depends on surfacing degraded health, not hiding
bad local state.

**Recommended capture:** Add corruption warnings to preflight/daily output and run-store
listing.

**Verification:** Inject malformed memory and run JSONL files; expect a warning or
degraded health item.

## RL-NEW-05: Sticky failure-card matching

**Type:** Defeat / memory relevance

Failure-card lookup can score raw word overlap, including common words, and then inject
prior task/error text into a new prompt.

**Why it matters:** Irrelevant prior failures can bias a new daily task or make the
agent overfit to an old problem.

**Recommended capture:** Add stopword filtering, thresholding, redaction, and tests for
unrelated tasks with common words.

**Verification:** Create two unrelated failures that share common words; ensure no
warning is injected unless stronger relevance signals match.
