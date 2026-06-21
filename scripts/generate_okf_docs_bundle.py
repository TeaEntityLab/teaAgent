"""Generate TeaAgent's deterministic OKF documentation catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from teaagent.okf import OKF_VERSION, validate_okf_bundle
from teaagent.path_safety import resolve_contained_path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_MANIFEST = _REPO_ROOT / 'docs' / 'okf-catalog.yaml'
_DEFAULT_OUTPUT = _REPO_ROOT / 'knowledge' / 'teaagent-current'
_TYPE_REGISTRY = {
    'Contract',
    'Architecture',
    'Decision Record',
    'Specification',
    'Guide',
    'Runbook',
    'Reference',
    'Plan',
    'Risk Record',
    'Evidence',
}
_H1_RE = re.compile(r'^#\s+(.+?)\s*$', re.MULTILINE)
_SLUG_RE = re.compile(r'[^a-z0-9]+')


@dataclass(frozen=True)
class CatalogEntry:
    source: str
    concept_type: str
    title: str
    description: str
    tags: tuple[str, ...]
    docs_tier: str
    authority: str
    lifecycle: str
    source_sha256: str
    slug: str


@dataclass(frozen=True)
class Catalog:
    okf_version: str
    bundle: str
    change_date: str
    change_summary: str
    entries: tuple[CatalogEntry, ...]


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError(
            'OKF catalog generation requires PyYAML; install teaagent[yaml]'
        ) from exc
    try:
        payload = yaml.safe_load(path.read_text(encoding='utf-8'))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f'invalid catalog manifest {path}: {exc}') from exc
    if not isinstance(payload, dict):
        raise ValueError('catalog manifest must be a YAML mapping')
    return payload


def _required_string(payload: dict[str, Any], key: str, *, context: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{context}.{key} must be a non-empty string')
    return value.strip()


def _source_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_title(path: Path) -> str:
    match = _H1_RE.search(path.read_text(encoding='utf-8'))
    if match is None:
        raise ValueError(f'catalog source requires an H1 heading: {path}')
    return match.group(1).strip()


def _source_slug(source: str) -> str:
    stem = source.removeprefix('docs/').removesuffix('.md').lower()
    slug = _SLUG_RE.sub('-', stem.replace('/', '--')).strip('-')
    if not slug or slug in {'index', 'log'}:
        raise ValueError(f'source produces a reserved or empty concept slug: {source}')
    return slug


def load_catalog(*, repo_root: Path, manifest_path: Path) -> Catalog:
    """Load and validate the catalog manifest and canonical sources."""
    repo_root = repo_root.resolve()
    manifest = resolve_contained_path(
        repo_root, manifest_path, must_exist=True, require_file=True
    )
    payload = _load_yaml(manifest)
    if payload.get('catalog_version') != 1:
        raise ValueError('catalog_version must be 1')
    okf_version = _required_string(payload, 'okf_version', context='catalog')
    if okf_version != OKF_VERSION:
        raise ValueError(
            f'catalog okf_version must be {OKF_VERSION!r}, found {okf_version!r}'
        )
    bundle = _required_string(payload, 'bundle', context='catalog')
    change_date = _required_string(payload, 'change_date', context='catalog')
    change_summary = _required_string(payload, 'change_summary', context='catalog')
    raw_documents = payload.get('documents')
    if not isinstance(raw_documents, list) or not raw_documents:
        raise ValueError('catalog.documents must be a non-empty list')

    entries: list[CatalogEntry] = []
    seen_sources: set[str] = set()
    seen_slugs: set[str] = set()
    for index, raw in enumerate(raw_documents):
        context = f'catalog.documents[{index}]'
        if not isinstance(raw, dict):
            raise ValueError(f'{context} must be a mapping')
        source = _required_string(raw, 'source', context=context)
        source_value = Path(source)
        if (
            source_value.is_absolute()
            or not source.startswith('docs/')
            or '..' in source_value.parts
        ):
            raise ValueError(f'{context}.source must be a relative path below docs/')
        if source in seen_sources:
            raise ValueError(f'duplicate catalog source: {source}')
        source_path = resolve_contained_path(
            repo_root, source, must_exist=True, require_file=True
        )
        try:
            source_path.relative_to((repo_root / 'docs').resolve())
        except ValueError as exc:
            raise ValueError(f'{context}.source must remain below docs/') from exc
        concept_type = _required_string(raw, 'type', context=context)
        if concept_type not in _TYPE_REGISTRY:
            raise ValueError(f'{context}.type is not registered: {concept_type}')
        docs_tier = _required_string(raw, 'docs_tier', context=context)
        lifecycle = _required_string(raw, 'lifecycle', context=context)
        if bundle == 'teaagent-current' and (
            docs_tier == 'archive' or lifecycle == 'historical'
        ):
            raise ValueError(
                f'archive document cannot enter teaagent-current: {source}'
            )
        raw_tags = raw.get('tags')
        if (
            not isinstance(raw_tags, list)
            or not raw_tags
            or not all(isinstance(tag, str) and tag.strip() for tag in raw_tags)
        ):
            raise ValueError(f'{context}.tags must be a non-empty string list')
        slug = _source_slug(source)
        if slug in seen_slugs:
            raise ValueError(f'duplicate concept slug: {slug}')
        entries.append(
            CatalogEntry(
                source=source,
                concept_type=concept_type,
                title=_source_title(source_path),
                description=_required_string(raw, 'description', context=context),
                tags=tuple(str(tag).strip() for tag in raw_tags),
                docs_tier=docs_tier,
                authority=_required_string(raw, 'authority', context=context),
                lifecycle=lifecycle,
                source_sha256=_source_digest(source_path),
                slug=slug,
            )
        )
        seen_sources.add(source)
        seen_slugs.add(slug)

    return Catalog(
        okf_version=okf_version,
        bundle=bundle,
        change_date=change_date,
        change_summary=change_summary,
        entries=tuple(sorted(entries, key=lambda entry: entry.source.lower())),
    )


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _render_concept(entry: CatalogEntry) -> str:
    tag_list = ', '.join(_quoted(tag) for tag in entry.tags)
    resource = f'urn:teaagent:doc:{entry.source}'
    return (
        '---\n'
        f'type: {_quoted(entry.concept_type)}\n'
        f'title: {_quoted(entry.title)}\n'
        f'description: {_quoted(entry.description)}\n'
        f'resource: {_quoted(resource)}\n'
        f'tags: [{tag_list}]\n'
        'teaagent:\n'
        f'  source_path: {_quoted(entry.source)}\n'
        f'  source_sha256: {_quoted(entry.source_sha256)}\n'
        f'  docs_tier: {_quoted(entry.docs_tier)}\n'
        f'  authority: {_quoted(entry.authority)}\n'
        f'  lifecycle: {_quoted(entry.lifecycle)}\n'
        '---\n\n'
        f'# {entry.title}\n\n'
        f'{entry.description}\n\n'
        f'Canonical source: `{entry.source}`\n'
    )


def render_catalog(catalog: Catalog) -> dict[str, str]:
    """Render every file in a catalog bundle without touching the filesystem."""
    index_lines = [
        '---',
        f'okf_version: {_quoted(catalog.okf_version)}',
        '---',
        '',
        '# TeaAgent Current Documentation',
        '',
    ]
    rendered: dict[str, str] = {}
    for entry in catalog.entries:
        concept_path = f'concepts/{entry.slug}.md'
        rendered[concept_path] = _render_concept(entry)
        index_lines.append(f'* [{entry.title}]({concept_path}) - {entry.description}')
    index_lines.append('')
    rendered['index.md'] = '\n'.join(index_lines)
    rendered['log.md'] = (
        '# TeaAgent Current Documentation Log\n\n'
        f'## {catalog.change_date}\n\n'
        f'- {catalog.change_summary}\n'
    )
    return rendered


def _write_tree(root: Path, rendered: dict[str, str]) -> None:
    for relative, content in sorted(rendered.items()):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')


def _validate_rendered_tree(root: Path) -> None:
    bundle = validate_okf_bundle(root.parent, root.name)
    errors = [finding for finding in bundle.findings if finding.severity == 'error']
    if errors:
        details = '; '.join(
            f'{finding.path}:{finding.code}:{finding.message}' for finding in errors
        )
        raise ValueError(f'generated OKF bundle is invalid: {details}')


def _resolve_output(repo_root: Path, output_path: Path) -> Path:
    output = resolve_contained_path(repo_root, output_path)
    relative = output.relative_to(repo_root.resolve())
    if relative == Path('.') or relative.parts[0] in {'.git', 'docs'}:
        raise ValueError(
            'catalog output must be below the repository and outside docs/'
        )
    return output


def generate_bundle(*, repo_root: Path, manifest_path: Path, output_path: Path) -> Path:
    """Generate and atomically replace a validated catalog bundle."""
    repo_root = repo_root.resolve()
    output = _resolve_output(repo_root, output_path)
    catalog = load_catalog(repo_root=repo_root, manifest_path=manifest_path)
    if output.name != catalog.bundle:
        raise ValueError(
            f'output directory must match catalog bundle {catalog.bundle!r}'
        )
    rendered = render_catalog(catalog)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f'.{output.name}.tmp-', dir=str(output.parent))
    )
    backup = output.with_name(f'.{output.name}.backup-{os.getpid()}')
    try:
        _write_tree(temporary, rendered)
        _validate_rendered_tree(temporary)
        if backup.exists():
            shutil.rmtree(backup)
        if output.exists():
            os.replace(output, backup)
        try:
            os.replace(temporary, output)
        except Exception:
            if backup.exists() and not output.exists():
                os.replace(backup, output)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup.exists() and output.exists():
            shutil.rmtree(backup)
    return output


def check_bundle(
    *, repo_root: Path, manifest_path: Path, output_path: Path
) -> list[str]:
    """Return actionable differences between expected and generated output."""
    repo_root = repo_root.resolve()
    output = _resolve_output(repo_root, output_path)
    catalog = load_catalog(repo_root=repo_root, manifest_path=manifest_path)
    if output.name != catalog.bundle:
        raise ValueError(
            f'output directory must match catalog bundle {catalog.bundle!r}'
        )
    rendered = render_catalog(catalog)
    if not output.is_dir():
        return [f'{output.relative_to(repo_root)} is missing; regenerate the catalog']

    errors: list[str] = []
    expected_paths = set(rendered)
    actual_paths = {
        path.relative_to(output).as_posix()
        for path in output.rglob('*')
        if path.is_file()
    }
    for entry in catalog.entries:
        concept_path = f'concepts/{entry.slug}.md'
        target = output / concept_path
        if (
            not target.is_file()
            or target.read_text(encoding='utf-8') != rendered[concept_path]
        ):
            errors.append(f'stale catalog entry for {entry.source}')
    for reserved in ('index.md', 'log.md'):
        target = output / reserved
        if (
            not target.is_file()
            or target.read_text(encoding='utf-8') != rendered[reserved]
        ):
            errors.append(f'stale generated file: {reserved}')
    for extra in sorted(actual_paths - expected_paths):
        errors.append(f'unexpected generated file: {extra}')
    try:
        bundle = validate_okf_bundle(output.parent, output.name)
    except (OSError, RuntimeError, ValueError) as exc:
        errors.append(f'generated bundle validation failed: {exc}')
    else:
        errors.extend(
            f'{finding.path}:{finding.code}:{finding.message}'
            for finding in bundle.findings
            if finding.severity == 'error'
        )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Generate TeaAgent documentation as a curated OKF bundle.'
    )
    parser.add_argument('--repo-root', default=str(_REPO_ROOT))
    parser.add_argument('--manifest', default=str(_DEFAULT_MANIFEST))
    parser.add_argument('--output', default=str(_DEFAULT_OUTPUT))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    manifest_path = Path(args.manifest)
    output_path = Path(args.output)
    try:
        if args.check:
            errors = check_bundle(
                repo_root=repo_root,
                manifest_path=manifest_path,
                output_path=output_path,
            )
            if errors:
                for error in errors:
                    print(error, file=sys.stderr)
                return 1
            print('OKF documentation catalog check passed.')
            return 0
        written = generate_bundle(
            repo_root=repo_root,
            manifest_path=manifest_path,
            output_path=output_path,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f'OKF catalog generation failed: {exc}', file=sys.stderr)
        return 1
    print(f'wrote {written}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
