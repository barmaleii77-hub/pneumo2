from __future__ import annotations

from pathlib import Path


def test_desktop_mnemo_page_exposes_pointer_preview_and_launcher() -> None:
    repo = Path(__file__).resolve().parents[1]
    src = (repo / "pneumo_solver_ui" / "pages" / "08_DesktopMnemo.py").read_text(encoding="utf-8")

    assert 'local_anim_latest_export_paths(EXPORTS_DIR, ensure_exists=False)' in src
    assert 'extract_anim_snapshot(raw_obj, source="desktop_mnemo_page")' in src
    assert "collect_anim_latest_diagnostics_summary" in src
    assert "build_anim_operator_recommendations" in src
    assert "read_desktop_mnemo_view_mode" in src
    assert "desktop_mnemo_view_mode_label" in src
    assert 'persisted_view_mode = read_desktop_mnemo_view_mode(PROJECT_ROOT)' in src
    assert 'persisted_view_mode_label = desktop_mnemo_view_mode_label(persisted_view_mode)' in src
    assert "Рекомендуемые действия перед запуском" in src
    assert "Режим открытия отдельного окна по умолчанию" in src
    assert "Разовый режим запуска окна" in src
    assert "Как сохранено" in src
    assert "Фокусный сценарий" in src
    assert "Полная схема" in src
    assert 'rec_col5.metric("Desktop view", persisted_view_mode_label)' in src
    assert 'st.warning("Сначала: " + operator_recommendations[0])' in src
    assert "def _launch_mnemo" in src
    assert "--startup-preset" in src
    assert "--startup-title" in src
    assert "--startup-view-mode" in src
    assert "--startup-check" in src
    assert "startup_view_mode: str = \"\"" in src
    assert "startup_view_mode=launch_view_mode" in src
    assert "Сценарный запуск" in src
    assert "Запустить preset:" in src
    assert "оперативный follow-разбор" in src
    assert "ретроспектива по текущему NPZ" in src
    assert "operational_follow_triage" in src
    assert "npz_retrospective_review" in src
    assert 'importlib.util.find_spec("PySide6.QtWebEngineWidgets")' in src
    assert '"pneumo_solver_ui.desktop_mnemo.main"' in src
    assert "Запустить Desktop Mnemo (follow)" in src
    assert "Запустить по текущему NPZ" in src
