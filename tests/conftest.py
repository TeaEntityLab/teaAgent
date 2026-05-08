from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Optional

from teaagent.llm import LLMResponse


class FakeAdapter:
    provider = 'fake'

    def __init__(
        self, outputs: list[str], *, before_each: Optional[Callable[[], None]] = None
    ) -> None:
        self.outputs = list(outputs)
        self.requests: list[object] = []
        self.before_each = before_each

    def complete(self, request: object) -> LLMResponse:
        if self.before_each is not None:
            self.before_each()
        self.requests.append(request)
        return LLMResponse(
            provider='fake', model='fake-model', content=self.outputs.pop(0)
        )


def fake_adapter(
    outputs: list[str], *, before_each: Optional[Callable[[], None]] = None
) -> FakeAdapter:
    return FakeAdapter(outputs, before_each=before_each)


def temp_workspace(*files: tuple[str, str]) -> tempfile.TemporaryDirectory[str]:
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    for relpath, content in files:
        filepath = root / relpath
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding='utf-8')
    return td
