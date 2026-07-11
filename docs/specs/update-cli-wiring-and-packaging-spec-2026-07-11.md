# Update CLI Wiring and Owner Packaging Spec (H6/M6)

> **Claim class:** Forward-looking specification (planned/held work — NOT current truth).
>
> **Status:** Preparation artifact for held item.
>
> **Date:** 2026-07-11
>
> **Trigger:** Owner request 2026-07-11 — forward-spec held/external roadmap items
> so future execution has pinned contracts and executable holds.
>
> **Scheduling gate (DR-006):** `friction-driven` — roadmap H6 records
> `update/*` as **intentionally not CLI-wired** (no `teaagent update` daily
> surface); wiring waits for an owner friction entry demanding it
> (`docs/roadmap-status.md` H6 row; `docs/work-log/roadmap-verification-2026-07-01.md`).
> M6 desktop packaging is Pending/Low confidence.
>
> **Owns:** The future `teaagent update` CLI contract, its wiring
> preconditions, and a compact M6/PKG-001 outline.
>
> **Does not own:** Current-truth status (`docs/roadmap-status.md`), the hold
> decision, prior H6 design intent (referenced below, not restated).
>
> **Review trigger:** An owner friction-log entry about updating/installing,
> or the M6 PKG-001 gate opening.

## 1. Current verified state (2026-07-11, HEAD)

Implemented and tested, **no CLI surface**:

| Module | Responsibility | Existing tests |
| --- | --- | --- |
| `teaagent/update/update.py` | `Version` parse/compare (`:30-112`), `UpdateChannel{stable,beta,nightly…}`, `UpdateChecker`, `UpdateServer` (default `base_url='https://api.teaagent.dev'`, `:156`) | `tests/test_update.py` |
| `teaagent/update/delta.py` | `DeltaGenerator/Applier/Manager`, `DeltaType` | `tests/test_update_delta.py` |
| `teaagent/update/installer.py` | `UpdateDownloader.verify_checksum` (`:150-165`), `_safe_extract` tar guard (`:168-177`), `UpdateInstaller`, `UpdateManager.rollback_last_update` | `tests/test_update_installer.py` |
| `teaagent/update/changelog.py` | changelog model/format/load | `tests/test_update_changelog.py` |
| `teaagent/governance/update_platform.py` | end-to-end v1→v2→rollback proof, `run_update_platform_proof` (`:67-122`), pure-local (tmp trees, no network) | `tests/test_update_platform_proof.py` |

CLI absence: `build_parser()` (`teaagent/cli/__init__.py:370`) registers no
`update` subcommand — verified by grep this pass and continuously by the hold
guard test (§4). Proof script: `scripts/prove_update_platform.py` (emits
`artifact_sha256`, `delta_sha256`, `rollback_ok`; ran green 2026-07-01 per
roadmap-verification; output is machine-local, not committed).

Prior design intent: `docs/specs/h4-h5-h6-usage-design.md` (Draft,
2026-06-09) and `docs/specs/h4-h5-h6-implementation-spec.md` cover H6
scenario framing — this spec supersedes neither; it adds the wiring contract
that was deliberately left out.

## 2. The hold and its gate

The owner has never hit update friction (the harness runs from the repo).
Harness-first §2 non-goals exclude adoption-driven packaging work. Therefore:
**no daily `update` surface until a friction entry demands it.** The update
machinery exists because H6 required a *proof of updateability*
(single-platform update proof), not a product feature.

## 3. Future contract

### 3.1 `teaagent update` CLI (activated by friction evidence only)

```
teaagent update check   [--channel stable|beta|nightly] [--json]
teaagent update apply   [--channel …] [--dry-run] [--yes] [--json]
teaagent update rollback [--json]
teaagent update status  [--json]
```

- **Exit codes:** 0 success/no-op; 1 operational failure; 2 refused by
  policy (unsigned, downgrade, dirty install dir). Distinct codes because
  automation must distinguish "nothing to do" from "refused".
- **`check`:** never mutates; offline-safe (network failure → exit 0 with
  `"status": "unknown", "reason": "offline"`; never a traceback).
- **`apply`:** requires an explicit confirmation (`--yes` or interactive
  prompt); `--dry-run` prints the resolved plan (current → target version,
  artifact hash, delta vs full) without touching disk. Backup-before-apply
  is mandatory (the existing `UpdateManager` backup/rollback mechanics).
- **`rollback`:** maps to `UpdateManager.rollback_last_update`; refuses
  (exit 2) when no backup exists (current behavior: FAILED + "No backup
  found", `tests/test_update_installer.py:229-233` — CLI must surface that
  as refusal, not crash).
- **Human vs `--json`:** plain-language first line ("Updated 1.2.3 → 1.3.0.
  Rollback available: teaagent update rollback"), JSON behind the flag —
  consistent with the receipts rule (harness-first §5.2).
- **Audit events:** `update_check`, `update_applied
  {from_version,to_version,artifact_sha256,channel}`, `update_rolled_back`,
  `update_refused {reason_code}` — appended to the workspace audit log so
  `teaagent show` can answer "what changed the binary".

### 3.2 Trust boundary (non-negotiable wiring preconditions)

1. **Signature verification before apply.** Default config refuses unsigned
   artifacts. Reuse the existing supply-chain surfaces: sigstore extra
   (`pyproject.toml:90-92`, `teaagent/sigstore_signer.py`) and the TSB
   provenance verifier. `--allow-unsigned` may exist for owner debugging but
   must emit `update_refused`-grade audit noise and be deny-by-default.
2. **Downgrade refusal.** `apply` refuses `target <= current`
   (exit 2, `reason_code: downgrade`). **Blocker:** `Version` prerelease
   ordering is lexicographic (`update.py:93-94`), so `rc.10 < rc.9` — semver
   numeric-identifier comparison disagrees. Either fix ordering or restrict
   channels to non-prerelease versions before wiring. Pinned by
   `test_prerelease_ordering_is_lexicographic_not_semver`.
3. **Equality/ordering totality.** `Version.__eq__` includes build metadata
   while `__lt__` ignores it (`update.py:79-108`): `1.0.0+b1` and `1.0.0+b2`
   are neither ordered nor equal. An update loop comparing artifact versions
   with build metadata could see a permanent "different but not newer"
   state. Pinned by `test_build_metadata_breaks_version_total_ordering`.
4. **Tar extraction hardening.** `_safe_extract` pre-scans members and
   raises on escape (`installer.py:168-177`) — the raise-contract is pinned
   by `test_safe_extract_refuses_parent_directory_traversal`. **Weakness
   (fix before wiring):** the check is a `str.startswith` prefix comparison
   (`installer.py:172`), which admits sibling-directory escapes when the
   sibling name shares the install dir as a string prefix (`…/install` vs
   `…/install-evil`). Replace with `Path.is_relative_to` (or
   `os.path.commonpath`) plus a symlink-member policy before any CLI
   exposure.
5. **Checksum chain.** `apply` verifies `verify_checksum` against the
   channel manifest before extraction; the manifest itself is covered by the
   signature in (1).

### 3.3 M6 / PKG-001 outline (Pending, Low confidence — labeled aspiration)

- Packaged launch smoke: a built artifact (wheel or platform bundle) starts,
  runs `teaagent doctor all`, exits 0 — CI-provable without a desktop.
- Signing/SBOM: `pip-audit` (security extra) + sigstore bundle per release
  artifact; SBOM emitted at build.
- Update docs: §3.1 becomes user-facing docs only at this milestone.
- Desktop session attach: out of scope for this spec beyond naming its gate
  (M6 PKG-001 acceptance) — no design here because zero friction evidence
  exists.

## 4. Executable specification

Tests live in `tests/test_update_wiring_spec.py`.

| Contract clause | Test | Kind |
| --- | --- | --- |
| No `update` subcommand in the CLI parser | `test_cli_has_no_update_subcommand` | guards hold today — failure = someone wired it; roadmap H6 row + this spec must change in the same commit |
| Prerelease ordering is lexicographic (downgrade-guard blocker) | `test_prerelease_ordering_is_lexicographic_not_semver` | baseline quirk pin |
| Build metadata breaks ordering totality | `test_build_metadata_breaks_version_total_ordering` | baseline quirk pin |
| `_safe_extract` raises on parent-directory traversal | `test_safe_extract_refuses_parent_directory_traversal` | guards trust boundary today |

Existing coverage (not duplicated): version parse/compare basics,
prerelease-vs-stable ordering, delta round-trips, installer backup/rollback,
platform proof (`tests/test_update*.py`,
`tests/test_update_platform_proof.py`).

## 5. Wiring-day checklist

1. Friction-log entry cited in the wiring PR (DR-006 T1).
2. Fix §3.2 blockers 2–4 (ordering, totality, prefix check) with tests.
3. Implement subcommands per §3.1; register in `build_parser()`; **delete
   the CLI-absence hold guard and update `docs/roadmap-status.md` H6 in the
   same commit** (the guard exists to force that coupling).
4. Signature verification wired and deny-by-default proven by an
   adversarial test (unsigned artifact → exit 2 + `update_refused`).
5. `teaagent doctor config` shows update channel + source; docs regen chain
   + `validate_docs_consistency.py` green.

## 6. Risks and open questions

- **Supply chain is the whole risk.** An update path is the highest-value
  target in the harness; that is exactly why it stays unwired until the
  trust boundary (§3.2) is complete — partial wiring is worse than none.
- **Prefix-collision extraction weakness** (§3.2.4) is unexploitable today
  (no production caller feeds attacker tars) but must not survive wiring.
- **Version quirks** (§3.2.2–3) are dormant until an update loop compares
  real artifact versions; the pins keep them visible.
- Open: should `update apply` require the workspace to be non-dirty
  (git-clean) when the install dir is a checkout? Default: yes, refuse with
  `reason_code: dirty_install`.
- Open: channel pinning per workspace vs per machine. Default: machine-level
  (`~/.teaagent`), because updates are a binary property, not a workspace
  property.
