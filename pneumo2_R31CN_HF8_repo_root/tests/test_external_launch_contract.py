from __future__ import annotations

import threading
import time

from pneumo_solver_ui.desktop_shell import external_launch


class _FakeProc:
    def __init__(self, gate: threading.Event, *, pid: int = 4242) -> None:
        self._gate = gate
        self.pid = pid
        self.wait_calls = 0

    def wait(self) -> int:
        self.wait_calls += 1
        self._gate.wait(timeout=1.0)
        return 0


def test_track_spawned_process_holds_reference_until_exit() -> None:
    gate = threading.Event()
    proc = _FakeProc(gate)
    external_launch._LIVE_PROCESSES.clear()

    tracked = external_launch.track_spawned_process(proc)  # type: ignore[arg-type]

    assert tracked is proc
    assert proc in external_launch._LIVE_PROCESSES
    assert proc.wait_calls in (0, 1)

    gate.set()
    for _ in range(50):
        if proc not in external_launch._LIVE_PROCESSES:
            break
        time.sleep(0.01)

    assert proc not in external_launch._LIVE_PROCESSES
    assert proc.wait_calls >= 1


def test_spawn_module_tracks_subprocess_handle(monkeypatch) -> None:
    gate = threading.Event()
    proc = _FakeProc(gate, pid=5252)
    external_launch._LIVE_PROCESSES.clear()

    def _fake_popen(*args, **kwargs):
        return proc

    monkeypatch.setattr(external_launch.subprocess, "Popen", _fake_popen)

    returned = external_launch.spawn_module("pkg.module")
    assert returned is proc
    assert proc in external_launch._LIVE_PROCESSES

    gate.set()
    for _ in range(50):
        if proc not in external_launch._LIVE_PROCESSES:
            break
        time.sleep(0.01)

    assert proc not in external_launch._LIVE_PROCESSES
