from __future__ import annotations

from pathlib import Path


def test_desktop_mnemo_page_exposes_pointer_preview_and_launcher() -> None:
    repo = Path(__file__).resolve().parents[1]
    src = (repo / "pneumo_solver_ui" / "pages" / "08_DesktopMnemo.py").read_text(encoding="utf-8")

    assert 'local_anim_latest_export_paths(EXPORTS_DIR, ensure_exists=False)' in src
    assert 'extract_anim_snapshot(raw_obj, source="desktop_mnemo_page")' in src
    assert "collect_anim_latest_diagnostics_summary" in src
    assert "build_anim_operator_recommendations" in src
    assert "Рекомендуемые действия перед запуском" in src
    assert 'st.warning("Сначала: " + operator_recommendations[0])' in src
    assert "def _launch_mnemo" in src
    assert "Сценарный запуск" in src
    assert "Запустить preset:" in src
    assert "оперативный follow-разбор" in src
    assert "ретроспектива по текущему NPZ" in src
    assert 'importlib.util.find_spec("PySide6.QtWebEngineWidgets")' in src
    assert '"pneumo_solver_ui.desktop_mnemo.main"' in src
    assert "Запустить Desktop Mnemo (follow)" in src
    assert "Запустить по текущему NPZ" in src
