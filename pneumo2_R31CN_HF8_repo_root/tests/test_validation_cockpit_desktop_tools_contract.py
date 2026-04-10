from __future__ import annotations

from pathlib import Path


def test_validation_cockpit_links_to_desktop_mnemo_and_animator() -> None:
    src = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "validation_cockpit_web.py").read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.entrypoints import desktop_animator_page_rel, desktop_mnemo_page_rel" in src
    assert "from pneumo_solver_ui.run_artifacts import collect_anim_latest_diagnostics_summary" in src
    assert "from pneumo_solver_ui.tools.send_bundle_contract import build_anim_operator_recommendations" in src
    assert "DESKTOP_MNEMO_PAGE = desktop_mnemo_page_rel(here=__file__)" in src
    assert "DESKTOP_ANIMATOR_PAGE = desktop_animator_page_rel(here=__file__)" in src
    assert "Связанные desktop-инструменты" in src
    assert "Открыть Desktop Mnemo" in src
    assert "Открыть Desktop Animator" in src
    assert "Журнал событий Desktop Mnemo" in src
    assert "collect_anim_latest_diagnostics_summary(" in src
    assert "operator_recommendations = build_anim_operator_recommendations(mnemo_event_diag)" in src
    assert "Рекомендуемые действия" in src
    assert 'st.warning("Сначала: " + operator_recommendations[0])' in src
