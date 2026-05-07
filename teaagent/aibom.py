from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class AIBOMComponent:
    kind: str
    name: str
    version: str
    digest: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AIBOMManifest:
    components: list[AIBOMComponent]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "teaagent.ai-bom.v1",
            "components": [
                {
                    "kind": component.kind,
                    "name": component.name,
                    "version": component.version,
                    "digest": component.digest,
                    "metadata": component.metadata,
                }
                for component in self.components
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def build_aibom(
    *,
    model: str,
    model_version: str,
    skill_paths: list[Path],
    mcp_server_card: Optional[Path] = None,
) -> AIBOMManifest:
    components = [
        AIBOMComponent(
            kind="model",
            name=model,
            version=model_version,
            digest="unavailable",
        )
    ]
    for skill_path in skill_paths:
        skill_file = skill_path / "SKILL.md" if skill_path.is_dir() else skill_path
        components.append(
            AIBOMComponent(
                kind="skill",
                name=skill_path.parent.name if skill_path.name == "SKILL.md" else skill_path.name,
                version="unversioned",
                digest=sha256_file(skill_file),
                metadata={"path": str(skill_file)},
            )
        )
    if mcp_server_card is not None:
        components.append(
            AIBOMComponent(
                kind="mcp_server_card",
                name=mcp_server_card.name,
                version="unversioned",
                digest=sha256_file(mcp_server_card),
                metadata={"path": str(mcp_server_card)},
            )
        )
    return AIBOMManifest(components=components)
