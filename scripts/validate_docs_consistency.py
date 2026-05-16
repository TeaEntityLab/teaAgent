from __future__ import annotations

import argparse
from importlib.util import module_from_spec, spec_from_file_location
import re
import subprocess
from pathlib import Path

TIER_START = "<!-- ACCEPTANCE_TIERS:START -->"
TIER_END = "<!-- ACCEPTANCE_TIERS:END -->"


def _render_tier_markdown() -> str:
    script = Path(__file__).with_name("run_acceptance_tier.py")
    spec = spec_from_file_location("run_acceptance_tier", script)
    if not spec or not spec.loader:
        raise RuntimeError("Unable to load run_acceptance_tier.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.render_tier_markdown()


def _extract_provider_count(readme_text: str) -> int:
    match = re.search(r"\((\d+)\s+providers\)", readme_text)
    if not match:
        raise ValueError("README provider count marker '(N providers)' not found.")
    return int(match.group(1))


def _extract_provider_env_vars(readme_text: str) -> set[str]:
    return set(re.findall(r"export\s+([A-Z0-9_]+_API_KEY)=", readme_text))


def _extract_acceptance_status_count(acceptance_text: str) -> int:
    match = re.search(r"`(\d+)\s+passed`", acceptance_text)
    if not match:
        raise ValueError("Acceptance status marker '`N passed`' not found.")
    return int(match.group(1))


def _collect_acceptance_test_files(acceptance_dir: Path) -> set[str]:
    return {path.name for path in acceptance_dir.glob("test_*.py")}


def _collect_acceptance_test_count(acceptance_dir: Path) -> int:
    result = subprocess.run(
        ["python3", "-m", "pytest", str(acceptance_dir), "--collect-only", "-q"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}"
    if result.returncode != 0:
        raise RuntimeError(f"Acceptance pytest collection failed.\n{output}")
    match = re.search(r"(\d+)\s+tests?\s+collected", output)
    if not match:
        raise ValueError("Could not parse collected test count from pytest output.")
    return int(match.group(1))


def _matrix_has_missing_use_cases(matrix_text: str) -> bool:
    return "| no |" in matrix_text


def _extract_marked_block(text: str, start: str, end: str) -> str:
    left = text.find(start)
    right = text.find(end)
    if left == -1 or right == -1 or right < left:
        raise ValueError(f"Marker block not found: {start} ... {end}")
    body = text[left + len(start) : right]
    return body.strip()


def validate_docs_consistency(
    *,
    readme_path: Path,
    acceptance_doc_path: Path,
    use_case_matrix_path: Path,
    acceptance_tests_dir: Path,
) -> list[str]:
    errors: list[str] = []

    readme_text = readme_path.read_text(encoding="utf-8")
    acceptance_text = acceptance_doc_path.read_text(encoding="utf-8")
    matrix_text = use_case_matrix_path.read_text(encoding="utf-8")
    acceptance_tests = _collect_acceptance_test_files(acceptance_tests_dir)

    try:
        provider_count = _extract_provider_count(readme_text)
    except ValueError as exc:
        errors.append(str(exc))
        provider_count = 0
    provider_env_count = len(_extract_provider_env_vars(readme_text))
    if provider_count and provider_count != provider_env_count:
        errors.append(
            "README provider mismatch: "
            f"(providers={provider_count}, env_vars={provider_env_count})."
        )

    try:
        status_count = _extract_acceptance_status_count(acceptance_text)
    except ValueError as exc:
        errors.append(str(exc))
        status_count = 0
    collected_count = _collect_acceptance_test_count(acceptance_tests_dir)
    if status_count and status_count != collected_count:
        errors.append(
            "Acceptance status mismatch: "
            f"docs/acceptance.md says {status_count} passed, "
            f"but pytest collect reports {collected_count} acceptance tests."
        )

    if not acceptance_tests:
        errors.append("No acceptance test files found under tests/acceptance.")

    if _matrix_has_missing_use_cases(matrix_text):
        errors.append("Use-case matrix contains uncovered rows ('Covered = no').")

    try:
        current_tier_block = _extract_marked_block(acceptance_text, TIER_START, TIER_END)
    except ValueError as exc:
        errors.append(str(exc))
    else:
        expected_tier_block = _render_tier_markdown().strip()
        if current_tier_block != expected_tier_block:
            errors.append(
                "Acceptance tier section is out of sync with scripts/run_acceptance_tier.py. "
                "Run: python3 scripts/sync_acceptance_tiers_doc.py"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate README / acceptance / use-case docs consistency."
    )
    parser.add_argument("--readme", default="README.md")
    parser.add_argument("--acceptance-doc", default="docs/acceptance.md")
    parser.add_argument("--use-case-matrix", default="docs/use-case-matrix.md")
    parser.add_argument("--acceptance-tests-dir", default="tests/acceptance")
    args = parser.parse_args()

    errors = validate_docs_consistency(
        readme_path=Path(args.readme),
        acceptance_doc_path=Path(args.acceptance_doc),
        use_case_matrix_path=Path(args.use_case_matrix),
        acceptance_tests_dir=Path(args.acceptance_tests_dir),
    )
    if errors:
        for err in errors:
            print(f"ERROR: {err}")
        return 1
    print("Docs consistency check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
