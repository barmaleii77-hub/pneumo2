from pathlib import Path
from types import SimpleNamespace

import pneumo_solver_ui.ui_runtime_helpers as runtime_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_ENTRYPOINTS = [
    REPO_ROOT / "pneumo_solver_ui" / "app.py",
    REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py",
]


def test_get_ui_nonce_and_fallback_play_detection_are_session_based(monkeypatch) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(runtime_helpers, "st", fake_st)

    nonce1 = runtime_helpers.get_ui_nonce()
    nonce2 = runtime_helpers.get_ui_nonce()
    assert nonce1 == nonce2
    assert len(nonce1) == 8

    fake_st.session_state["mech2d_fb_demo::play"] = True
    assert runtime_helpers.is_any_fallback_anim_playing() is True
    fake_st.session_state["mech2d_fb_demo::play"] = False
    fake_st.session_state["unrelated::play"] = True
    assert runtime_helpers.is_any_fallback_anim_playing() is False


def test_proc_metrics_pid_alive_and_do_rerun(monkeypatch) -> None:
    class FakeProcess:
        pid = 123

        @staticmethod
        def memory_info():
            return SimpleNamespace(rss=3 * 1024 * 1024, vms=7 * 1024 * 1024)

        @staticmethod
        def cpu_num():
            return 2

        @staticmethod
        def cpu_percent(interval=None):
            assert interval is None
            return 12.5

    fake_psutil = SimpleNamespace(
        Process=lambda _pid: FakeProcess(),
        cpu_count=lambda logical=True: 16 if logical else 8,
    )
    monkeypatch.setattr(runtime_helpers, "_HAS_PSUTIL", True)
    monkeypatch.setattr(runtime_helpers, "psutil", fake_psutil)
    monkeypatch.setattr(runtime_helpers.os, "getpid", lambda: 999)

    metrics = runtime_helpers.proc_metrics()
    assert metrics == {
        "pid": 123,
        "rss_mb": 3.0,
        "vms_mb": 7.0,
        "cpu_num": 2,
        "cpu_count": 16,
        "cpu_percent": 12.5,
    }

    proc = SimpleNamespace(poll=lambda: None)
    done = SimpleNamespace(poll=lambda: 0)
    assert runtime_helpers.pid_alive(proc) is True
    assert runtime_helpers.pid_alive(done) is False
    assert runtime_helpers.pid_alive(None) is False

    fake_st = SimpleNamespace(session_state={})
    calls = []
    monkeypatch.setattr(runtime_helpers, "st", fake_st)
    monkeypatch.setattr(runtime_helpers, "request_rerun", lambda st_mod: calls.append(st_mod))
    runtime_helpers.do_rerun()
    assert calls == [fake_st]


def test_large_ui_entrypoints_import_shared_runtime_helpers() -> None:
    for path in UI_ENTRYPOINTS:
        src = path.read_text(encoding="utf-8")
        assert "from pneumo_solver_ui.ui_runtime_helpers import (" in src
        assert "proc_metrics as _proc_metrics" in src
        assert "def get_ui_nonce(" not in src
        assert "def _proc_metrics(" not in src
        assert "def is_any_fallback_anim_playing(" not in src
        assert "def pid_alive(" not in src
        assert "def do_rerun(" not in src
        assert "request_rerun(st)" not in src
