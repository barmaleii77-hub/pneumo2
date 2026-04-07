from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "pneumo_solver_ui"
PAGE = ROOT / "pages" / "03_Optimization.py"


def test_r31cr_optimization_page_surfaces_workspace_run_history_without_hiding_controls() -> None:
    src = PAGE.read_text(encoding="utf-8")
    assert '"Последовательные запуски в текущем workspace"' in src
    assert 'discover_workspace_optimization_runs' in src
    assert 'format_run_choice' in src
    assert 'autoload_to_session(st.session_state)' in src
    assert '"Сделать текущей «последней оптимизацией»"' in src
    assert '"Открыть результаты выбранного run"' in src
    assert '"Если вы запускаете оптимизации последовательно' in src
