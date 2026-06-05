"""Long-Result Envelope helpers.

Wraps large tool outputs (>50KB) in an envelope with preview, truncation
metadata, artifact_path, content_hash, and cursor.  Full artifacts are stored
in ``.teaagent/artifacts/tool-results/``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from teaagent.audit import secure_audit_dir, secure_audit_file
from teaagent.storage import atomic_write_text

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MAX_PREVIEW_BYTES: int = 50_000  # 50 KB


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LongResultEnvelope:
    """Metadata envelope for a (potentially large) tool result.

    When the full content fits within *max_preview_bytes* the envelope is
    returned with ``truncated=False`` and no ``artifact_path``.  Otherwise the
    full content is persisted to disk and only a preview is kept in the
    envelope.
    """

    content_type: str
    """MIME-type of the content, e.g. ``"text/markdown"``."""

    preview: str
    """First *preview_bytes* characters of the content."""

    truncated: bool
    """``True`` when the content was larger than the preview threshold."""

    total_bytes: int
    """Full content length in bytes (UTF-8)."""

    preview_bytes: int
    """Length of the preview string in bytes (UTF-8)."""

    artifact_path: str
    """Relative workspace path to the full artifact file, or ``""``."""

    content_hash: str
    """``"sha256:<hexdigest>"`` of the full content."""

    cursor: str
    """``"offset:<bytes_read>"`` for paginated read-back."""

    suggested_next_action: str
    """Human-readable hint for the caller, e.g.
    ``"readback_artifact(workspace_root, artifact_path, ...)"``."""


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def store_long_result(
    workspace_root: Path,
    run_id: str,
    tool_call_id: str,
    content: str,
    content_type: str = "text/markdown",
    *,
    max_preview_bytes: int = DEFAULT_MAX_PREVIEW_BYTES,
) -> LongResultEnvelope:
    """Inspect *content* and create a :class:`LongResultEnvelope`.

    If the content is small enough to be previewed in full the envelope is
    returned without writing anything to disk.  Otherwise the full content is
    persisted to ``.teaagent/artifacts/tool-results/<run_id>/<tool_call_id>.txt``
    and only the preview is kept in-memory.
    """
    content_bytes = content.encode("utf-8")
    total_bytes = len(content_bytes)
    content_hash = _sha256_hex(content_bytes)

    # Small content -- no artifact needed.
    if total_bytes <= max_preview_bytes:
        return LongResultEnvelope(
            content_type=content_type,
            preview=content,
            truncated=False,
            total_bytes=total_bytes,
            preview_bytes=total_bytes,
            artifact_path="",
            content_hash=content_hash,
            cursor=f"offset:{total_bytes}",
            suggested_next_action="full content available in preview",
        )

    # Large content -- persist artifact, keep preview.
    artifact_dir = _artifact_dir(workspace_root, run_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    secure_audit_dir(artifact_dir)

    artifact_file = artifact_dir / f"{_safe_name(tool_call_id)}.txt"
    atomic_write_text(artifact_file, content)
    secure_audit_file(artifact_file)

    preview_data, preview_actual_bytes = _safe_utf8_truncate(
        content_bytes, max_preview_bytes
    )
    preview = preview_data.decode("utf-8")

    return LongResultEnvelope(
        content_type=content_type,
        preview=preview,
        truncated=True,
        total_bytes=total_bytes,
        preview_bytes=len(preview.encode("utf-8")),
        artifact_path=str(
            artifact_file.relative_to(workspace_root)
        ),
        content_hash=content_hash,
        cursor=f"offset:{len(preview.encode('utf-8'))}",
        suggested_next_action=(
            f"readback_artifact(workspace_root, '{_rel_path(workspace_root, artifact_file)}', cursor='{_cursor_str(len(preview.encode('utf-8')))}')"
        ),
    )


_ARTIFACT_STORE_REL = ".teaagent/artifacts/tool-results"


def _validate_artifact_path(workspace_root: Path, artifact_path: str) -> Path:
    """Resolve and validate *artifact_path* is inside the artifact store.

    Raises ``ValueError`` if the path is absolute, contains traversal, or
    points outside ``.teaagent/artifacts/tool-results/``.
    """
    if Path(artifact_path).is_absolute():
        raise ValueError(
            f"absolute path not allowed in readback_artifact: {artifact_path}"
        )
    resolved = (workspace_root / artifact_path).resolve()
    store_root = (workspace_root / _ARTIFACT_STORE_REL).resolve()
    if not str(resolved).startswith(str(store_root) + "/") and resolved != store_root:
        raise ValueError(
            f"path outside artifact store ({_ARTIFACT_STORE_REL}/): {artifact_path}"
        )
    return resolved


def readback_artifact(
    workspace_root: Path,
    artifact_path: str,
    cursor: str | None = None,
    *,
    max_bytes: int = 50_000,
) -> str:
    """Read (a slice of) a stored artifact.

    Parameters
    ----------
    workspace_root:
        Absolute workspace root.
    artifact_path:
        Path relative to *workspace_root*, e.g.
        ``".teaagent/artifacts/tool-results/<run_id>/<tool_id>.txt"``.
    cursor:
        Optional cursor string of the form ``"offset:<N>"``.  When supplied,
        reading starts at byte offset *N*.
    max_bytes:
        Maximum bytes to return (default 50KB).
    """
    if max_bytes <= 0:
        raise ValueError(f"max_bytes must be positive, got {max_bytes}")
    full_path = _validate_artifact_path(workspace_root, artifact_path)
    content_bytes = full_path.read_bytes()

    offset = _parse_offset(cursor)
    if offset < 0:
        raise ValueError(f"cursor offset must be >= 0, got {offset}")
    chunk_data, _ = _safe_utf8_truncate(
        content_bytes[offset : offset + max_bytes], max_bytes
    )
    return chunk_data.decode("utf-8")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sha256_hex(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _safe_utf8_truncate(data: bytes, max_bytes: int) -> tuple[bytes, int]:
    """Truncate *data* to at most *max_bytes* at a valid UTF-8 boundary.

    Returns ``(truncated_data, actual_byte_count)``.  If *data* is already
    within the limit or *max_bytes* is zero, returns the unchanged data.
    """
    if len(data) <= max_bytes or max_bytes <= 0:
        return data, len(data)
    truncated = data[:max_bytes]
    while truncated:
        try:
            truncated.decode("utf-8")
            return truncated, len(truncated)
        except UnicodeDecodeError:
            truncated = truncated[:-1]
    return b"", 0


def _artifact_dir(workspace_root: Path, run_id: str) -> Path:
    return workspace_root / ".teaagent" / "artifacts" / "tool-results" / _safe_name(run_id)


def _safe_name(identifier: str) -> str:
    """Strip characters that could cause path traversal / ambiguity."""
    return "".join(ch for ch in identifier if ch.isalnum() or ch in {"-", "_"}) or "unnamed"


def _rel_path(workspace_root: Path, absolute: Path) -> str:
    return str(absolute.relative_to(workspace_root))


def _cursor_str(offset: int) -> str:
    return f"offset:{offset}"


def _parse_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    if cursor.startswith("offset:"):
        try:
            return int(cursor[len("offset:"):])
        except ValueError:
            return 0
    return 0
