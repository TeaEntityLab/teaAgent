---
feature: operator-cli
source_commit: a91f1dc2
last_verified_at: 2026-09-24
verification_status: passed
covers:
  - teaagent/cli/__init__.py
  - teaagent/cli/_handlers/_doctor/
  - teaagent/cli/_handlers/_misc.py
  - teaagent/cli/_handlers/_cockpit.py
  - teaagent/wizard.py
  - teaagent/preflight.py
  - teaagent/daily.py
  - teaagent/cockpit.py
  - teaagent/selftest.py
drive:
  - id: tests
    expect: first-run/preflight/daily/cockpit/doctor test set passes (~44 tests, ~4s)
    run: |
      cd "$REPO"
      "$P" -m pytest -q tests/test_first_run.py tests/test_dogfood_first_run_g23_g38.py \
        tests/test_preflight.py tests/test_daily.py tests/test_cockpit.py \
        tests/test_dogfood_doctor_wizard_tty_g38_twin.py tests/test_dogfood_run_list_schema_g26.py
  - id: init-non-tty-requires-provider
    expect: init without --provider on non-TTY stdin exits 1 with {"ok":false,…"provider is required…"} and writes nothing
    run: |
      mkdir fresh && cd fresh && git init -q
      rc=0; "$T" init --root . < /dev/null > out.json 2> /dev/null || rc=$?
      [ "$rc" = 1 ]
      jget 'd["ok"], "provider is required" in d["message"]' < out.json | grep -qx '(False, True)'
      [ ! -e .teaagent ] && [ ! -e AGENTS.md ]
  - id: init-fake
    expect: init --provider fake writes .teaagent/config.{json,toml}, AGENTS.md, and adds .teaagent/ to .gitignore
    run: |
      mkdir fresh && cd fresh && git init -q
      "$T" init --root . --provider fake | jget 'd["ok"], d["provider"], d["gitignore"]' | grep -qx "(True, 'fake', 'added')"
      [ -s .teaagent/config.toml ] && [ -s AGENTS.md ] && grep -qx '.teaagent/' .gitignore
  - id: doctor-selftest
    expect: "`doctor all` reports the fake provider ok (exit is 1 whenever any provider lacks a key, 0 only when all pass); `selftest` reports ok with the read-only permission smoke"
    run: |
      rc=0; "$T" doctor all --root . > doctor.json || rc=$?
      [ "$rc" = 0 ] || [ "$rc" = 1 ]
      jget '[p["ok"] for p in d["checks"]["providers"] if p["provider"] == "fake"]' < doctor.json | grep -qx '\[True\]'
      "$T" selftest --root . | jget 'd["ok"], d["permission_smoke"]["ok"]' | grep -qx '(True, True)'
  - id: read-only-surfaces
    expect: status/daily --dry-run/preflight/cockpit answer without a model call and without touching the workspace tree; preflight exits 2 when the task needs clarification, 0 when it does not
    run: |
      "$T" status --root . > status.txt; grep -q 'status=idle' status.txt
      "$T" daily "summarize" --dry-run --root . | jget 'd["dry_run"]' | grep -qx True
      rc=0; "$T" preflight "summarize" --root . > pre.json || rc=$?
      [ "$rc" = 2 ]; jget 'd["clarification"]["needs_clarification"]' < pre.json | grep -qx True
      "$T" preflight "summarize README.md into three bullet points in SUMMARY.md" --root . | jget 'd["clarification"]["needs_clarification"]' | grep -qx False
      "$T" cockpit --root . | jget '"pending_approvals" in d' | grep -qx True
      rm -f status.txt pre.json
      [ -z "$(git status --porcelain)" ]
---

# Operator CLI

Everyday operator commands that do not execute tools: first-run
(`init`/`setup`, `teaagent/wizard.py`), environment checks (`doctor`,
`selftest`), and read-only situational surfaces (`status`, `daily`,
`preflight`, `cockpit`). Parser: `teaagent/cli/__init__.py`
(`teaagent = "teaagent.cli:main"`).

## Entry points

| Surface | Command |
|---|---|
| First run | `teaagent init --root . --provider fake` (legacy) / `teaagent setup` (guided) |
| Checks | `teaagent doctor {all,providers,project,config,mcp,git-sandbox,selftest,…} --root .`; `teaagent selftest --root .` |
| Situational | `teaagent status`, `teaagent daily "<task>" --dry-run`, `teaagent preflight "<task>"`, `teaagent cockpit` |
| Help | `teaagent surfaces explain` (bare `surfaces` is a usage error, exit 2), `teaagent <cmd> --help` |

## Observable outcomes (healthy product)

- Non-interactive `init`/`setup` without `--provider` fail fast (exit 1, JSON `ok:false`) and write nothing (`docs/cli.md` § init).
- `doctor all` lists every provider with `ok` true/false; missing keys for real providers are expected on a keyless machine.
- `status`, `daily --dry-run`, `preflight`, `cockpit` never call a model and never modify the tree.

## Failure paths

| Symptom | Likely class |
|---|---|
| non-TTY init silently picks a provider or writes files | product regression |
| a read-only surface dirties the git tree | product regression |
| `doctor` subcommand given a path (`doctor --root .`) → usage error | harness: `doctor` requires a subcommand (`doctor all`) |
| JSON piped into a consumer that exits early → `Unexpected error: [Errno 32] Broken pipe` | harness: consume the whole stream (`> file`, then parse) |

## Evidence

`verify/checks/drive.sh operator-cli`.
