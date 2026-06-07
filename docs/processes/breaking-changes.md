# Breaking Changes Process

1. **Propose** — Open an ADR describing the change, migration path, and timeline.
2. **Announce** — Add a "Breaking Changes" entry under `CHANGELOG.md` Unreleased.
3. **Deprecate** — Ship deprecation warnings for at least one minor release when possible.
4. **Migrate** — Provide migration guide in `docs/` or ADR consequences section.
5. **Remove** — Delete deprecated APIs only after the announced window.

## Version policy

- **Public API** (`teaagent` exports, documented CLI): deprecate in X.Y, remove in X.(Y+1) or next major.
- **Internal modules** (`teaagent._*`, undocumented CLI): may change in any release.

## Checklist

- [ ] ADR merged
- [ ] CHANGELOG updated
- [ ] Tests cover old and new behavior during migration window
- [ ] `scripts/pre-release-check.sh` passes
