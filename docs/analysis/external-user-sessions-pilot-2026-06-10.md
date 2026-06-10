# External User Sessions — Pilot Evidence — 2026-06-10

**Work item:** WDH-002 (partial — tooling + simulated pilots)  
**Status:** Simulated pilots recorded; non-maintainer sessions still required.

## What was captured

Three **simulated pilot** sessions using the WDC-002 progressive-disclosure copy
via `scripts/capture_stranger_session.py`. These are **not** substitutes for
non-maintainer user sessions — they validate the capture harness and happy-path
concept budget.

| Participant | Type | Happy-path concepts | Completed |
| --- | --- | ---: | --- |
| pilot-01 | simulated_pilot | 3 | yes |
| pilot-02 | simulated_pilot | 3 | yes |
| pilot-03-advanced | simulated_pilot | 3 (+ advanced disclosed) | yes |

Machine-readable artifact: [external-user-sessions-pilot-2026-06-10.json](external-user-sessions-pilot-2026-06-10.json)

## Remaining gate

Recruit **≥ 3 non-maintainer** participants per
[external-user-session-protocol-2026-06-10.md](external-user-session-protocol-2026-06-10.md)
with screen recording + terminal log + questionnaire.

## Tooling

- `teaagent/governance/stranger_session.py`
- `scripts/capture_stranger_session.py`
- `tests/test_stranger_session_capture.py`
