from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "pneumo_solver_ui"
PAGE = ROOT / "pages" / "03_Optimization.py"
HISTORY_UI = ROOT / "optimization_workspace_history_ui.py"


def test_r31cr_optimization_page_surfaces_workspace_run_history_without_hiding_controls() -> None:
    src = PAGE.read_text(encoding="utf-8")
    history_src = HISTORY_UI.read_text(encoding="utf-8")
    combined = src + "\n" + history_src
    assert '"Последовательные запуски в текущем workspace"' in src
    assert 'render_workspace_run_history_block' in src
    assert 'discover_workspace_optimization_runs' in combined
    assert 'format_run_choice' in combined
    assert 'render_selected_optimization_run_details' in combined
    assert 'render_optimization_run_pointer_actions' in combined
    assert '"Сделать текущей «последней оптимизацией»"' in combined
    assert '"Открыть результаты выбранного run"' in combined
    assert '"Если вы запускаете оптимизации последовательно' in combined
