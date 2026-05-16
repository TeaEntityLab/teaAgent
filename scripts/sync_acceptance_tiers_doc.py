from __future__ import annotations

import argparse
from pathlib import Path

from run_acceptance_tier import render_tier_markdown

START = "<!-- ACCEPTANCE_TIERS:START -->"
END = "<!-- ACCEPTANCE_TIERS:END -->"


def sync_acceptance_tiers_doc(*, acceptance_doc: Path) -> None:
    text = acceptance_doc.read_text(encoding="utf-8")
    start = text.find(START)
    end = text.find(END)
    if start == -1 or end == -1 or end < start:
        raise ValueError("Acceptance tier markers not found in docs/acceptance.md.")
    prefix = text[: start + len(START)]
    suffix = text[end:]
    block = "\n\n" + render_tier_markdown().rstrip() + "\n\n"
    acceptance_doc.write_text(prefix + block + suffix, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync docs/acceptance.md tier section from scripts/run_acceptance_tier.py."
    )
    parser.add_argument("--acceptance-doc", default="docs/acceptance.md")
    args = parser.parse_args()
    sync_acceptance_tiers_doc(acceptance_doc=Path(args.acceptance_doc))
    print("Synced acceptance tiers section.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
