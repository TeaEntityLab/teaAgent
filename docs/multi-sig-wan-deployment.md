# WAN multi-sig deployment

Configure HTTP signature relay URLs in workspace policy so `ApprovalPolicy` loads
them automatically from `.teaagent/config.json`.

## 1. Collector (requester workspace)

Copy [templates/multi-sig/config.json.example](../templates/multi-sig/config.json.example)
to `.teaagent/config.json` and set:

- `local_relay_base_url` — public URL of **this** workspace's signature relay
- `peer_relay_urls` — map each `peer_agent_ids` entry to that peer's relay base URL

Start the collector relay (behind TLS termination in production):

```bash
teaagent sync signature-relay serve \
  --host 127.0.0.1 --port 8791 \
  --api-token-file .teaagent/relay-tokens.json
```

Export for peers signing remotely:

```bash
export TEAAGENT_SIGNATURE_RELAY_TOKEN="<token from relay-tokens.json>"
```

## 2. Peer workspaces

Each peer runs its own relay and receives approval requests via HTTP POST from the
requester. After review, peers submit signatures:

```bash
teaagent sync signature-relay submit \
  --relay-url https://collector.example:8791 \
  --request-id "<request_id>" \
  --peer-id peer-a \
  --signature "<ssh-signature-blob>"
```

## 3. Verification

- `uv.lock` pins `jaraco-context` 6.1.2+ (CVE-2026-23949 / Dependabot #10)
- `teaagent selftest` reports `jaraco_context.ok: true` when the package is installed
- Run `TEAAGENT_PRECOMMIT_FULL=1 pre-commit run --all-files` before release tags

## Related

- [http-surface-auth.md](http-surface-auth.md) — bearer tokens and relay headers
- [ADR 0008](adr/0008-p4-strategic-posture.md) — strategic posture
