# ADR 0008: P4 strategic posture (storage, TLS, P2P auth)

## Status

Accepted — incremental delivery; full multi-node production remains future work.

## Context

Post-audit remediation P1–P3 closed harness correctness, docs, and CI gates.
P4 items are quarter-scale: distributed JSONL, MCP TLS, authenticated P2P
multi-sig transport, and transitive dependency hygiene (Dependabot #10 /
CVE-2026-23949 on `jaraco.context`).

## Decisions

### 1. JSONL locking and NFS

- **Single-node / single-writer workspace:** keep `fcntl.LOCK_EX` on audit and
  memory JSONL; `atomic_write_text` for RunStore and federated state files.
- **NFS or multi-writer shared roots:** not supported for JSONL stores; operators
  must use one writer per workspace or migrate hot paths to SQLite/Postgres
  (OAuth store and Context Bus already SQLite-backed).
- **Migration path (future):** optional `SQLiteAuditStore` / shared DB for
  RunStore behind feature flags — not started in P4 tranche.

### 2. MCP TLS

- **No native TLS in `serve_mcp_http`** — same as ADR 0005; terminate TLS at
  Caddy/nginx (see `templates/reverse-proxy/`).
- **`TEAAGENT_STRICT_LOCAL=1`** requires bearer/OAuth even on loopback for MCP HTTP.

### 3. Authenticated P2P multi-sig (file transport)

- File-based multi-sig remains **experimental** (not production WAN transport).
- **P4 tranche:** optional `TEAAGENT_FEDERATED_SIGNATURE_TOKEN` — signature JSON
  files must carry matching `auth_token` when the env var is set.
- **P4.3b (shipped):** HTTP signature relay (`teaagent sync signature-relay serve`,
  `SignatureRelayClient`, `MultiSigQuorumConfig.peer_relay_urls` /
  `local_relay_base_url`). Bearer tokens reuse relay token files / env
  (`TEAAGENT_SIGNATURE_RELAY_TOKEN`, `TEAAGENT_RELAY_TOKEN`).

### 4. `jaraco.context` (CVE-2026-23949)

- Constrain transitive installs to **`jaraco-context>=6.1.0`** via `[tool.uv]`
  `constraint-dependencies` in `pyproject.toml`.
- Security selftest verifies installed version when the package is present.

## Consequences

- Operators on NFS must not run concurrent TeaAgent writers on the same JSONL paths.
- WAN MCP requires reverse proxy TLS; multi-sig uses signature relay + bearer tokens.
- Dependabot alert #10 should clear once GitHub rescans `uv.lock` at 6.1.2+.

## Alternatives considered

- **Native MCP TLS:** rejected — duplicates proxy features and cert rotation burden.
- **Immediate JSONL→DB migration:** deferred — large schema and replay compatibility work.
