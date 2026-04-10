from __future__ import annotations

from pathlib import Path


def test_desktop_animator_page_exposes_pointer_preview_launcher_and_guidance() -> None:
    repo = Path(__file__).resolve().parents[1]
    src = (repo / "pneumo_solver_ui" / "pages" / "08_DesktopAnimator.py").read_text(encoding="utf-8")

    assert 'local_anim_latest_export_paths(EXPORTS_DIR, ensure_exists=False)' in src
    assert 'extract_anim_snapshot(raw_obj, source="desktop_animator_page")' in src
    assert "collect_anim_latest_diagnostics_summary" in src
    assert "build_anim_operator_recommendations" in src
    assert "Рекомендуемые действия перед запуском" in src
    assert 'st.warning("Сначала: " + operator_recommendations[0])' in src
    assert "def _launch_animator" in src
    assert "Сценарный запуск" in src
    assert "Запустить preset:" in src
    assert "follow с low-load (--no-gl)" in src
    assert "multi-view follow" in src
    assert '"pneumo_solver_ui.desktop_animator.main"' in src
    assert "Запустить Desktop Animator (follow)" in src
    assert "Запустить Desktop Animator (пустой)" in src
