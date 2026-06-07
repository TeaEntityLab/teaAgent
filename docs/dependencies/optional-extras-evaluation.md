# Optional Dependency Extras Evaluation (DEP-004)

Audit of `pyproject.toml` optional dependency groups and recommended disposition.

| Extra | Purpose | Usage | Recommendation |
|-------|---------|-------|----------------|
| `config` | TOML config on Python <3.11 | Common | **Keep** — small, widely used |
| `file-watching` | watchdog memory watcher | Optional feature | **Keep** — graceful fallback without it |
| `tui` | prompt-toolkit REPL | Primary UX | **Keep** in monorepo |
| `code-analysis` | tree-sitter relations | Code tools | **Keep** — core differentiator |
| `graphqlite` | Graph persistence | Niche deployments | **Keep optional** — candidate for split package if maintenance grows |
| `playwright` | Browser tools | Optional automation | **Keep optional** |
| `crypto` / `oauth` / `audit-encryption` | OAuth + encrypted audit | Security paths | **Keep** — shared via `teaagent[crypto]` |
| `managed-google-adk` | Google ADK runtime | Narrow cloud use | **Keep optional** — extract if unused in 2 releases |
| `managed-vertex` | Vertex AI | Narrow cloud use | **Keep optional** — same as ADK |
| `telemetry` | OpenTelemetry | Observability | **Keep** |
| `anthropic` | Anthropic SDK | Provider adapter | **Keep** |
| `yaml` | YAML skill/config parsing | Skills | **Keep** |
| `wasm` | wasmer sandbox | Highly specialized | **Keep optional** — top extraction candidate |
| `release` | build/twine | Maintainers only | **Keep** |
| `security` | pip-audit | CI | **Keep** |
| `sigstore` | Release signing | Release pipeline | **Keep optional** |
| `github` | GitHub integration | Optional workflow | **Keep optional** |
| `dev` | Full developer stack | Contributors | **Keep** |

## Extraction candidates (future)

1. **`wasm`** — isolated sandbox backend, heavy native dep
2. **`managed-google-adk` + `managed-vertex`** — cloud-only, large transitive tree
3. **`graphqlite`** — alternate persistence backend

No removals recommended in this release; document-only evaluation complete.
