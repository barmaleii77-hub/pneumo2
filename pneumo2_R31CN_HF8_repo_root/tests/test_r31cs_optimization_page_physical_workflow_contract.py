from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "pneumo_solver_ui"
PAGE = ROOT / "pages" / "03_Optimization.py"


def test_r31cs_optimization_page_surfaces_physical_workflow_and_sequential_history() -> None:
    src = PAGE.read_text(encoding="utf-8")
    assert '"Физический смысл путей запуска"' in src
    assert 'StageRunner — physics-first путь' in src
    assert 'Distributed coordinator — длинный trade study' in src
    assert 'powertrain / engine-map модели в live optimization contract сейчас нет' in src
    assert '"Вернуть канонический objective stack (comfort / roll / energy)"' in src
    assert 'discover_workspace_optimization_runs' in src
    assert 'format_run_choice' in src
    assert '"Последовательные запуски в текущем workspace"' in src
    assert '"Сделать текущей «последней оптимизацией»"' in src
    assert '"Открыть результаты выбранного run"' in src
    assert 'Нормальный инженерный сценарий: сначала StageRunner как быстрый physical gate' in src
