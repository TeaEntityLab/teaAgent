from __future__ import annotations

import test_support


def test_can_start_threads_requires_requested_concurrent_capacity(monkeypatch) -> None:
    created: list[FakeThread] = []

    class FakeThread:
        starts = 0

        def __init__(self, *, target) -> None:
            self.target = target
            self.joined = False
            created.append(self)

        def start(self) -> None:
            type(self).starts += 1
            if type(self).starts == 3:
                raise RuntimeError("can't start new thread")

        def join(self, timeout: float | None = None) -> None:
            self.joined = True

    monkeypatch.setattr(test_support.threading, 'Thread', FakeThread)

    assert not test_support.can_start_threads(4)
    assert len(created) == 3
    assert created[0].joined
    assert created[1].joined


def test_can_start_threads_keeps_threads_alive_until_all_are_started(
    monkeypatch,
) -> None:
    created: list[FakeThread] = []

    class FakeThread:
        def __init__(self, *, target) -> None:
            self.target = target
            self.joined = False
            created.append(self)

        def start(self) -> None:
            return None

        def join(self, timeout: float | None = None) -> None:
            self.joined = True

    monkeypatch.setattr(test_support.threading, 'Thread', FakeThread)

    assert test_support.can_start_threads(3)
    assert len(created) == 3
    assert all(thread.joined for thread in created)
