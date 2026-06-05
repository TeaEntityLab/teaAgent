# RSS Summary Skill Reference

## What This Skill Does

Guides an LLM to parse an OPML feed list file, extract RSS/Atom feed URLs,
fetch and parse each feed's XML content, and produce a source-backed markdown
summary. Each feed item is rendered with a linked title and attribution.
Suspicious content (including prompt injection) is detected, quoted, and never
followed.

## Limitations

1. **No runtime code.** This skill is a prompt-only guide. It contains no
   Python runtime code that fetches RSS feeds. All execution happens through
   the LLM interpreting these instructions and using available tools.

2. **Offline / fixture mode only.** The skill is designed for offline use
   with local fixture files. It does not perform real network calls in the
   TeaAgent harness; feeds are read as local files resolved relative to the
   OPML file location.

3. **Synthetic fixtures.** The acceptance test uses synthetic fixture files
   at `tests/skills/fixtures/rss/`. Real-world RSS feeds may use Atom format
   or non-standard XML structures not covered by the fixture set.

4. **No Atom support in fixtures.** The fixture XML files use RSS 2.0 format
   only. Atom feed parsing is described in general terms but is not tested.

5. **No incremental updates.** The skill produces a full summary each time.
   There is no mechanism for caching, diff-based updates, or tracking
   previously seen items.

6. **Single-OPML only.** The skill processes one OPML file per invocation.
   Multi-file or subscription management is out of scope.

## Example Usage

Load the skill explicitly:
```bash
teaagent skill explain --skill rss-summary --root .
```

Run with fixtures:
```bash
teaagent agent run gpt \
  "Read the RSS fixtures from tests/skills/fixtures/rss/ and produce a markdown summary" \
  --permission-mode read-only --skill rss-summary --root .
```

## Known Failure Modes

- **Missing OPML file.** If the OPML file path is incorrect or the file is
  absent, the skill will report no feeds found.
- **Malformed XML.** If a feed file contains invalid XML, parsing will fail
  for that feed. The skill should report the error and continue with remaining
  feeds.
- **Large feeds.** Feeds with many items may produce very long summaries.
  There is no built-in truncation or pagination.
- **Injection bypass.** The pattern-matching for prompt injection is
  heuristic and may miss obfuscated injection text (e.g., character
  substitutions, encoding tricks).

## Fixture Reference

| File | Contents |
|------|----------|
| `feeds.opml` | OPML with two feed entries: Small Tech Blog and Large Tech Blog |
| `small_feed.xml` | RSS 2.0 feed with 2 items |
| `large_feed.xml` | RSS 2.0 feed with 12 items, including one prompt injection item |

## Progressive Disclosure

The `SKILL.md` file contains the workflow instructions. This `REFERENCE.md`
documents limitations, known failure modes, and fixture details that are not
needed during normal skill execution.
