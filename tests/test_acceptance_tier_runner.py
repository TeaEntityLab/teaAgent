from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_acceptance_tier.py"
_SPEC = spec_from_file_location("run_acceptance_tier", _SCRIPT)
assert _SPEC and _SPEC.loader
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
tier_paths = _MODULE.tier_paths
render_tier_markdown = _MODULE.render_tier_markdown


def test_tier_paths_for_p0() -> None:
    paths = tier_paths("p0", acceptance_dir=Path("tests/acceptance"))
    assert any(path.endswith("test_daily_cli.py") for path in paths)
    assert any(path.endswith("test_policy_as_code_flow.py") for path in paths)


def test_tier_paths_for_all() -> None:
    paths = tier_paths("all", acceptance_dir=Path("tests/acceptance"))
    assert paths == ["tests/acceptance"]


def test_render_tier_markdown_contains_p0_p1_p2() -> None:
    markdown = render_tier_markdown()
    assert "| P0 |" in markdown
    assert "| P1 |" in markdown
    assert "| P2 |" in markdown
