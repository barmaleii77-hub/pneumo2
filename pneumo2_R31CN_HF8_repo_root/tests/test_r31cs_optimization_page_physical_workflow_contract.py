from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "pneumo_solver_ui"
PAGE = ROOT / "pages" / "03_Optimization.py"
READONLY_UI = ROOT / "optimization_page_readonly_ui.py"
HISTORY_UI = ROOT / "optimization_workspace_history_ui.py"
LAUNCH_SESSION_UI = ROOT / "optimization_launch_session_ui.py"


def test_r31cs_optimization_page_surfaces_physical_workflow_and_sequential_history() -> None:
    src = PAGE.read_text(encoding="utf-8")
    readonly_src = READONLY_UI.read_text(encoding="utf-8")
    history_src = HISTORY_UI.read_text(encoding="utf-8")
    launch_session_src = LAUNCH_SESSION_UI.read_text(encoding="utf-8")
    combined = src + "\n" + readonly_src + "\n" + history_src + "\n" + launch_session_src
    assert '"Физический смысл путей запуска"' in src
    assert 'render_physical_workflow_block' in src
    assert 'StageRunner — быстрый путь по физике' in combined
    assert 'Distributed coordinator — длинный перебор вариантов' in combined
    assert 'powertrain / engine-map модели в live optimization contract сейчас нет' in combined
    assert '"Вернуть канонический набор целей (comfort / roll / energy)"' in combined
    assert 'discover_workspace_optimization_runs' in combined
    assert 'format_run_choice' in combined
    assert '"Последовательные запуски в текущем workspace"' in src
    assert 'render_workspace_run_history_block' in src
    assert '"Сделать текущей «последней оптимизацией»"' in combined
    assert '"Открыть результаты выбранного run"' in combined
    assert 'Нормальный инженерный сценарий: сначала StageRunner как быстрый физический фильтр' in combined
