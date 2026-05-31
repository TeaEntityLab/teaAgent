from __future__ import annotations

import pytest

from teaagent.code_mode._child_process import ChildProcessCodeModeBackend
from teaagent.code_mode._types import CodeModeSandbox


def test_child_process_backend_rejects_untrusted_mode() -> None:
    backend = ChildProcessCodeModeBackend(trusted_only=False)
    with pytest.raises(ValueError, match='ContainerCodeModeBackend'):
        backend.execute('1+1', {}, CodeModeSandbox(timeout_seconds=1))
