# EFX live proof — not run, 2026-10-23

> **Claim class:** Dated execution note. Not a status change.
> **Owner:** docs
> **Last reviewed:** 2026-10-23

The owner said to run the live proof. The procedure in
[efx-live-proof-procedure-2026-08-31.md](../plans/efx-live-proof-procedure-2026-08-31.md)
blocks the live call until all six Definition of Ready rows are filled:
throwaway target, credential scope, exact payload and call budget, pre-state,
reversal, and interruption authorization. None of those values was given.
No GitHub, browser, or other provider call was made. EFX-001 through EFX-003
stay in progress.

Providerless checks from that procedure's dry-run section passed on this
machine the same day: `tests/test_efx002_effect_classification.py`,
`tests/test_efx003_one_time_approval.py`,
`tests/test_efx001_interrupted_dispatch.py`, and
`tests/acceptance/test_efx_durable_effect_flow.py` (15 tests). That is the
same evidence the procedure already treats as not live proof.

The blank worksheet to fill before any live call is sample 3 in
[owner-experiment-samples-2026-10-23.md](owner-experiment-samples-2026-10-23.md).
Filling the worksheet is not authorization to run the call.
