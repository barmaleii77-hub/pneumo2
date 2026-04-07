from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "pneumo_solver_ui"
PAGE = ROOT / "pages" / "03_Optimization.py"


def test_r31cf_optimization_page_preserves_soft_stop_contract() -> None:
    src = PAGE.read_text(encoding="utf-8")
    assert 'stop_file: Optional[Path] = None' in src
    assert 'def _write_soft_stop_file(' in src
    assert 'def _soft_stop_requested(' in src
    assert 'def _terminate_process(' in src
    assert 'STOP_OPTIMIZATION.txt' in src
    assert '"Стоп (мягко)"' in src
    assert '"Стоп (жёстко)"' in src
    assert '.write_text("stop", encoding="utf-8")' in src
    assert 'stop_file=plan.stop_file' in src


def test_r31cf_optimization_page_marks_stop_requested_runs_honestly() -> None:
    src = PAGE.read_text(encoding="utf-8")
    assert 'if rc == 0 and _soft_stop_requested(job):' in src
    assert '"Оптимизация остановлена по STOP-файлу' in src
    assert '"Запрошена мягкая остановка через STOP_OPTIMIZATION.txt.' in src
