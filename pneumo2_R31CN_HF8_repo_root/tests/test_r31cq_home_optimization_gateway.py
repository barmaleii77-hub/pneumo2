from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
PAGE = ROOT / "pneumo_solver_ui" / "pages" / "03_Optimization.py"
REGISTRY = ROOT / "pneumo_solver_ui" / "page_registry.py"


def test_home_page_exposes_gateway_and_not_second_live_control_plane() -> None:
    src = UI.read_text(encoding="utf-8")
    assert 'st.subheader("Оптимизация — отдельная страница")' in src
    assert '"🎯 Открыть страницу оптимизации"' in src
    assert '"📊 Результаты оптимизации / ExperimentDB"' in src
    assert 'Главная больше не держит второй launcher оптимизации' in src
    assert 'Legacy home optimization block retained only as dormant source surface' in src
    assert 'Live launch path = dedicated Optimization page.' in src
    assert '"Seed/promotion policy"' in src
    assert 'load_last_optimization_pointer_snapshot' in src
    assert 'return load_last_optimization_pointer_snapshot()' in src
    assert 'render_last_optimization_pointer_summary' in src
    assert '"System Influence eps_rel"' in src


def test_page_registry_and_dedicated_optimization_page_reflect_new_split() -> None:
    reg_src = REGISTRY.read_text(encoding="utf-8")
    page_src = PAGE.read_text(encoding="utf-8")
    assert 'Оптимизация — на отдельной странице' in reg_src
    assert 'Главная страница держит search-space contract' in page_src
    assert '"🏠 Главная: входные данные и suite"' in page_src
    assert '"📊 Результаты оптимизации"' in page_src
    assert '"🗄️ База оптимизаций"' in page_src
