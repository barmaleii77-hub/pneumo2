from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.entrypoints import (
    UiEntrypointSpec,
    canonical_home_page,
    canonical_home_page_rel,
    canonical_streamlit_entrypoint,
    canonical_streamlit_entrypoint_rel,
    desktop_animator_page_rel,
    desktop_mnemo_page_rel,
    env_diagnostics_page_rel,
    legacy_single_page_entrypoint,
    legacy_single_page_entrypoint_rel,
    ui_entrypoint_specs,
    validation_web_page_rel,
)


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_entrypoint_helper_points_to_root_app_and_home_page() -> None:
    assert canonical_streamlit_entrypoint(here=__file__) == ROOT / "app.py"
    assert canonical_home_page(here=__file__) == ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
    assert legacy_single_page_entrypoint(here=__file__) == ROOT / "pneumo_solver_ui" / "app.py"
    assert canonical_streamlit_entrypoint_rel(here=__file__) == "app.py"
    assert canonical_home_page_rel(here=__file__) == "pneumo_solver_ui/pneumo_ui_app.py"
    assert legacy_single_page_entrypoint_rel(here=__file__) == "pneumo_solver_ui/app.py"
    assert desktop_animator_page_rel(here=__file__) == "pneumo_solver_ui/pages/08_DesktopAnimator.py"
    assert desktop_mnemo_page_rel(here=__file__) == "pneumo_solver_ui/pages/08_DesktopMnemo.py"
    assert validation_web_page_rel(here=__file__) == "pneumo_solver_ui/pages/09_Validation_Web.py"
    assert env_diagnostics_page_rel(here=__file__) == "pneumo_solver_ui/pages/99_EnvDiagnostics.py"


def test_ui_entrypoint_specs_capture_canonical_home_and_legacy_roles() -> None:
    specs = ui_entrypoint_specs(here=__file__)
    assert specs == (
        UiEntrypointSpec(
            key="canonical_shell",
            rel_path="app.py",
            role="Canonical Streamlit shell launched by START_PNEUMO_APP and manual streamlit run app.py.",
        ),
        UiEntrypointSpec(
            key="home_page",
            rel_path="pneumo_solver_ui/pneumo_ui_app.py",
            role="Heavy multipage home screen rendered inside the canonical shell.",
        ),
        UiEntrypointSpec(
            key="legacy_single_page",
            rel_path="pneumo_solver_ui/app.py",
            role="Legacy single-page package UI kept for compatibility and source-level regression guards.",
        ),
    )


def test_launchers_and_headless_smokes_use_canonical_streamlit_entrypoint() -> None:
    files = [
        ROOT / "pneumo_solver_ui" / "tools" / "launch_ui.py",
        ROOT / "pneumo_solver_ui" / "tools" / "run_full_diagnostics.py",
        ROOT / "pneumo_solver_ui" / "tools" / "run_autotest.py",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "from pneumo_solver_ui.entrypoints import canonical_streamlit_entrypoint" in text
        assert "canonical_streamlit_entrypoint(here=__file__)" in text


def test_calibration_page_docs_reference_root_streamlit_app() -> None:
    text = (ROOT / "pneumo_solver_ui" / "pages" / "02_Calibration_NPZ.py").read_text(encoding="utf-8")
    assert "python -m streamlit run app.py" in text
    assert "python -m streamlit run pneumo_ui_app.py" not in text


def test_page_registry_and_preflight_use_canonical_relative_targets() -> None:
    page_registry = (ROOT / "pneumo_solver_ui" / "page_registry.py").read_text(encoding="utf-8")
    assert "from pneumo_solver_ui.entrypoints import canonical_home_page_rel, repo_root" in page_registry
    assert "home_rel = canonical_home_page_rel(here=__file__)" in page_registry

    ui_preflight = (ROOT / "pneumo_solver_ui" / "ui_preflight.py").read_text(encoding="utf-8")
    for helper_name in [
        "canonical_home_page_rel",
        "desktop_animator_page_rel",
        "desktop_mnemo_page_rel",
        "validation_web_page_rel",
        "env_diagnostics_page_rel",
        "local_anim_latest_export_paths",
        "extract_anim_snapshot",
        "_pick_next_page_canonical",
        "_pick_next_page = _pick_next_page_canonical",
        "DESKTOP_MNEMO_PAGE",
        'steps["mnemo"]',
    ]:
        assert helper_name in ui_preflight
    assert "local_anim_latest_export_paths(exports_dir, ensure_exists=False)" in ui_preflight
    assert 'extract_anim_snapshot(obj, source="ui_preflight_pointer")' in ui_preflight


def test_selfcheck_uses_entrypoint_inventory_instead_of_hardcoded_ui_paths() -> None:
    text = (ROOT / "pneumo_solver_ui" / "tools" / "selfcheck.py").read_text(encoding="utf-8")
    assert "from pneumo_solver_ui.entrypoints import ui_entrypoint_specs" in text
    assert "ui_entrypoint_specs(here=__file__)" in text
