from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.streamlit_compat import request_rerun


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "pneumo_solver_ui"


class _FakeModernStreamlit:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def rerun(self) -> None:
        self.calls.append("rerun")


class _FakeLegacyStreamlit:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def experimental_rerun(self) -> None:
        self.calls.append("experimental_rerun")


class _FakeNoRerunStreamlit:
    pass


def test_r31cn_request_rerun_prefers_modern_streamlit_api() -> None:
    fake = _FakeModernStreamlit()
    assert request_rerun(fake) is True
    assert fake.calls == ["rerun"]


def test_r31cn_request_rerun_falls_back_to_legacy_api_only_when_needed() -> None:
    fake = _FakeLegacyStreamlit()
    assert request_rerun(fake) is True
    assert fake.calls == ["experimental_rerun"]


def test_r31cn_request_rerun_returns_false_when_no_rerun_api_exists() -> None:
    fake = _FakeNoRerunStreamlit()
    assert request_rerun(fake) is False


def test_r31cn_runtime_sources_use_shared_rerun_helper_without_direct_experimental_calls() -> None:
    for rel in [
        "pneumo_solver_ui/pages/03_Optimization.py",
        "pneumo_solver_ui/pages/15_PneumoScheme_Mnemo.py",
        "pneumo_solver_ui/compare_npz_web.py",
        "pneumo_solver_ui/app.py",
        "pneumo_solver_ui/pneumo_ui_app.py",
    ]:
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "request_rerun" in src or "do_rerun" in src
        assert "st.experimental_rerun(" not in src


def test_r31cn_optimization_page_exposes_one_active_launch_mode_and_one_explicit_start_button() -> None:
    src = (UI_ROOT / "pages" / "03_Optimization.py").read_text(encoding="utf-8")
    launch_src = (UI_ROOT / "optimization_launch_session_ui.py").read_text(encoding="utf-8")
    combined = src + "\n" + launch_src
    assert '"Активный путь запуска"' in src
    assert '"Сейчас активен только один путь запуска.' in src
    assert 'if not opt_use_staged:' in src
    assert 'if opt_use_staged:' in src
    assert 'render_optimization_launch_session_block' in src
    assert 'launch_button_label = (' in launch_src
    assert '"Запустить StageRunner"' in combined
    assert '"Запустить distributed coordinator"' in combined
    assert 'render_optimization_launch_panel' in combined
    assert '"**Что нажимать:** выберите режим выше' in combined
