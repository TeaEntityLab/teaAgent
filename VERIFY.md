# VERIFY — TeaAgent verification map

Control surface for a **fresh agent** (no prior conversation) to launch, doctor,
drive, and classify failures in this repo. Map files live under `verify/`:

| Path | Role |
|---|---|
| `verify/features/*.md` | one file per feature area: metadata, `covers:` paths, runnable `drive:` items, outcomes, failure paths |
| `verify/acceptance.yaml` | **locked** oracle: 6 highest-value invariants (2 `known_failing`) |
| `verify/checks/` | `doctor.sh`, `drive.sh`, `acceptance.sh`, `verify-map.sh`, shared `lib.sh` |
| `verify/fixtures/` | offline fake-provider scripts |
| `verify/sweep.sh`, `verify/refresh.sh`, `verify/run-verifier.sh` | fresh-agent sweep, map-refresh loop, agent run interface |
| `verify/governance/` | contracts for **agents launched by `sweep.sh`/`refresh.sh`** (`verifier-agent.md` expects an `## Assignment` those scripts append), delivery/authority contracts, handover |

**Verifying by hand or as a directly-invoked agent?** You have no per-feature
assignment: run Doctor, then every feature (`drive.sh all`), then
`acceptance.sh`, and classify each failure with the table below. Ignore
`verifier-agent.md`'s Assignment section; it applies only inside `sweep.sh`.

Map verified at `a91f1dc2` on 2026-09-24 (macOS arm64, bash 3.2, Python 3.12.8).

## Launch

The product is a Python CLI + library (`teaagent = "teaagent.cli:main"`), plus
an optional MCP server (`teaagent mcp serve`). Everything below runs offline:
the `fake` provider needs no API key.

Prerequisite: a repo virtualenv at `.venv` with dev extras
(setup: `CONTRIBUTING.md`, first code block). Scripts use `.venv/bin/teaagent`
and `.venv/bin/python`; override with `TEAAGENT_BIN` / `PYTHON_BIN`.

```bash
.venv/bin/teaagent --version
```

Drive items never run in the repo: each gets a fresh git workspace under
`$TMPDIR` initialised with `teaagent init --provider fake`, with `HOME`
redirected into it (so `~/.teaagent/run-keys` stays out of your real home).

## Doctor (fast smoke)

```bash
verify/checks/doctor.sh           # ~5s: CLI boots, selftest, tool lint, offline run, audit chain
verify/checks/doctor.sh --tests   # + repo smoke test tier (~25s)
```

Exit 0 = healthy, 1 = product check failed, 4 = harness broken.

## Drive

```bash
verify/checks/drive.sh all                        # every feature (~2 min alone, ~4-5 min under parallel load)
verify/checks/drive.sh governed-tool-execution    # one feature
verify/checks/acceptance.sh                       # locked oracle: PASS / FAIL / XFAIL / XPASS
verify/checks/verify-map.sh                       # map health: lock, staleness, drive, acceptance
```

Features (index and known findings: `verify/features/README.md`):

| Feature | Covers |
|---|---|
| `governed-tool-execution` | permission modes, exact-call approval, presets, plan gate, tool contracts |
| `run-lifecycle` | offline runs, iteration/tool-call caps, runs list/replay, undo |
| `audit-evidence` | per-run JSONL events, redaction, hash-chain verify, denial explanations |
| `mcp-surface` | `mcp serve` stdio/HTTP protocol, auth, sessions (known finding F-1) |
| `operator-cli` | init/setup error contract, doctor/selftest, status/daily/preflight/cockpit |

Reproduce one drive item by hand (copy its `run:` body after these two lines):

```bash
source verify/checks/lib.sh
enter_scratch      # cd into a fresh scratch workspace; sets W, HOME, T, P, FIX
```

## Evidence

`drive.sh` and `acceptance.sh` print one line per item and a `logs:` directory;
each log starts with `scratch: <dir>` and is then a `set -x` trace, so the last
traced command is the one that failed. `grep -q` hides output: inspect the
files the item wrote in that scratch dir (it is kept) or rerun the item by hand.
Quote the PASS/FAIL lines and the failing log tail as evidence. A green run is
evidence for the listed items only, not for unmapped features.

## Failure classification

|Class|Meaning|Repair|
|---|---|---|
|Product regression|Product behavior changed for the worse|Report; never edit map/spec/tests to match|
|Doc drift|Docs no longer match a healthy product|Update the doc|
|Spec/oracle error|The acceptance spec or test expectation is wrong|Oracles read-only; propose change for review|
|Harness failure|Toolchain, launch, environment, external dep broke|Fix the harness|

How to decide:

1. `doctor.sh` exit 4, missing `.venv`, port in use, `mk_scratch failed` → **harness failure**.
2. A drive item or `expected_pass` acceptance check fails → read the log and the
   product source under the feature's `covers:`. Product now violates the
   item's `expect` or an `AGENTS.md` invariant → **product regression**.
3. Product is healthy by source and tests but a feature file's command, flag,
   field, or exit code is wrong → **doc drift** (fix the feature file).
4. `acceptance.yaml` asserts something the owner-approved behavior never
   promised → **spec/oracle error** (propose; do not edit the oracle).
5. `XFAIL` = a documented known finding still reproduces (not a new failure);
   a feature whose only problems are XFAIL known findings verdicts **PASS**, with the finding ids noted.
   `XPASS` = a known finding stopped reproducing → update
   `verify/features/README.md` and the owning feature (doc drift), then propose
   flipping the oracle status to `expected_pass`.

## Environment quirks (verbatim)

- `teaagent runs list --root .` → `teaagent: error: unrecognized arguments: --root .`; write `teaagent runs --root . list`.
- `teaagent doctor --root .` → usage error; `doctor` needs a subcommand (`doctor all`).
- `doctor all` exits 1 on any machine missing a real provider key; the fake provider still reports `ok`.
- `teaagent plan` and `teaagent preflight` exit 2 when the task needs clarification (`ready: false`) but still print JSON (and `plan` still writes the artifact).
- `workspace-write` runs need a plan (`Error [PLAN_GATE]`, exit 2) unless `--skip-plan-check`.
- Piping CLI JSON into a reader that closes early → `Unexpected error: [Errno 32] Broken pipe`; write to a file first.
- Stock macOS has no `timeout(1)`; `run-verifier.sh` applies `AGENT_TIMEOUT` only when `timeout`/`gtimeout` exists.
- `CONTRIBUTING.md` installs `.[dev,oauth,telemetry]`; `pyproject.toml` defines no `oauth` extra. The installer warns and continues (uv: ``warning: The package `teaagent @ file://…` does not have an extra named `oauth` ``). This repo's `.venv` is uv-managed and has no `pip` module.

## Fresh-agent sweep and map refresh

```bash
verify/sweep.sh     # one read-only verifier agent per feature; tally in $STATE/summary.md
verify/refresh.sh   # loop: re-verify stale features until verify-map.sh holds (edits verify/features/*.md only)
```

Both call the host agent through `verify/run-verifier.sh` (default `claude -p`
with a tool allowlist; `AGENT_CMD` overrides, e.g. for stub dry runs). Exit
codes are in each script header. Before the first **unattended** run, a human
approves caps, allowlist, and blast radius (`verify/governance/HANDOVER.md`).

## Maintenance

Event-driven: when a commit touches a feature's `covers:` paths,
`verify-map.sh` reports it `STALE`. Re-run that feature's drive, fix prose
drift, then bump `source_commit`, `last_verified_at`, `verification_status`.
A failing drive means the product changed — classify before editing the map.
`drive:` blocks and everything outside `verify/features/*.md` change only by a
reviewed commit, never inside `refresh.sh`.

## Cleanup

```bash
rm -rf "${TMPDIR:-/tmp}"/teaagent-verify.* "${TMPDIR:-/tmp}"/teaagent-verify-logs.* "${TMPDIR:-/tmp}"/teaagent-sweep.* "${TMPDIR:-/tmp}"/teaagent-refresh
```

Nothing is written inside the repo. An HTTP drive item that was killed mid-run
can leave a `teaagent mcp serve --http` process: `pkill -f 'teaagent mcp serve --http'`.
