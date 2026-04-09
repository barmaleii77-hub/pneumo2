from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_results_secondary_views_helpers as helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_secondary_views_helpers.py"
SURFACE_SECTION_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"


def test_render_secondary_results_views_dispatches_to_each_shared_section() -> None:
    calls: list[tuple[str, object]] = []

    handled_flow = helpers.render_secondary_results_views(
        "st",
        view_res="Потоки",
        flow_view_label="Потоки",
        energy_audit_view_label="Энерго-аудит",
        animation_view_label="Анимация",
        render_flow_section_fn=lambda st, **kwargs: calls.append(("flow", kwargs["token"])),
        flow_section_kwargs={"token": "flow-token"},
        render_energy_audit_section_fn=lambda st, **kwargs: calls.append(("energy", kwargs["token"])),
        energy_audit_section_kwargs={"token": "energy-token"},
        render_animation_section_fn=lambda st, **kwargs: calls.append(("anim", kwargs["token"])),
        animation_section_kwargs={"token": "anim-token"},
    )
    handled_energy = helpers.render_secondary_results_views(
        "st",
        view_res="Энерго-аудит",
        flow_view_label="Потоки",
        energy_audit_view_label="Энерго-аудит",
        animation_view_label="Анимация",
        render_flow_section_fn=lambda st, **kwargs: calls.append(("flow-2", kwargs["token"])),
        flow_section_kwargs={"token": "flow-token-2"},
        render_energy_audit_section_fn=lambda st, **kwargs: calls.append(("energy", kwargs["token"])),
        energy_audit_section_kwargs={"token": "energy-token"},
        render_animation_section_fn=lambda st, **kwargs: calls.append(("anim-2", kwargs["token"])),
        animation_section_kwargs={"token": "anim-token-2"},
    )
    handled_anim = helpers.render_secondary_results_views(
        "st",
        view_res="Анимация",
        flow_view_label="Потоки",
        energy_audit_view_label="Энерго-аудит",
        animation_view_label="Анимация",
        render_flow_section_fn=lambda st, **kwargs: calls.append(("flow-3", kwargs["token"])),
        flow_section_kwargs={"token": "flow-token-3"},
        render_energy_audit_section_fn=lambda st, **kwargs: calls.append(("energy-2", kwargs["token"])),
        energy_audit_section_kwargs={"token": "energy-token-2"},
        render_animation_section_fn=lambda st, **kwargs: calls.append(("anim", kwargs["token"])),
        animation_section_kwargs={"token": "anim-token"},
    )
    handled_unknown = helpers.render_secondary_results_views(
        "st",
        view_res="Неизвестно",
        flow_view_label="Потоки",
        energy_audit_view_label="Энерго-аудит",
        animation_view_label="Анимация",
        render_flow_section_fn=lambda st, **kwargs: calls.append(("flow-4", kwargs["token"])),
        flow_section_kwargs={"token": "flow-token-4"},
        render_energy_audit_section_fn=lambda st, **kwargs: calls.append(("energy-4", kwargs["token"])),
        energy_audit_section_kwargs={"token": "energy-token-4"},
        render_animation_section_fn=lambda st, **kwargs: calls.append(("anim-4", kwargs["token"])),
        animation_section_kwargs={"token": "anim-token-4"},
    )

    assert handled_flow is True
    assert handled_energy is True
    assert handled_anim is True
    assert handled_unknown is False
    assert calls == [
        ("flow", "flow-token"),
        ("energy", "energy-token"),
        ("anim", "anim-token"),
    ]


def test_entrypoints_use_shared_secondary_results_dispatch_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    surface_section_text = SURFACE_SECTION_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_results_secondary_views_helpers import (" not in app_text
    assert "from pneumo_solver_ui.ui_results_secondary_views_helpers import (" not in heavy_text
    assert "render_secondary_results_views(" not in app_text
    assert "render_secondary_results_views(" not in heavy_text
    assert 'elif view_res == "Потоки"' not in app_text
    assert 'elif view_res == "Потоки"' not in heavy_text
    assert 'elif view_res == "Энерго‑аудит"' not in app_text
    assert 'elif view_res == "Энерго-аудит"' not in heavy_text
    assert 'elif view_res == "Анимация"' not in app_text
    assert 'elif view_res == "Анимация"' not in heavy_text
    assert '"render_secondary_results_views_fn": render_secondary_results_views' in surface_section_text
    assert "render_flow_section_fn(st, **flow_section_kwargs)" in helper_text
    assert "render_energy_audit_section_fn(st, **energy_audit_section_kwargs)" in helper_text
    assert "render_animation_section_fn(st, **animation_section_kwargs)" in helper_text
