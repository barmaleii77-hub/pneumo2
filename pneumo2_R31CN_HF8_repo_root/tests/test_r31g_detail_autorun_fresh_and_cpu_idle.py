from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_pneumo_ui_app_uses_fresh_detail_autorun_policy():
    src = (ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")
    assert "arm_detail_autorun_after_baseline" in src
    assert "should_bypass_detail_disk_cache" in src
    assert "clear_detail_force_fresh" in src
    assert "detail_force_fresh_key" in src
    assert "detail_cache_bypassed_after_baseline" in src


def test_mech_car3d_no_longer_spins_raf_when_hidden_or_tiny():
    src = (ROOT / "pneumo_solver_ui" / "components" / "mech_car3d" / "index.html").read_text(encoding="utf-8")
    assert "if (W < 10 || H < 10) { requestAnimationFrame(renderFrame); return; }" not in src
    assert "__frameInParentViewport" in src
    assert "__nextIdleMs" in src


def test_follower_components_have_parent_viewport_idle_guards():
    rels = [
        ("pneumo_solver_ui/components/mech_anim/index.html"),
        ("pneumo_solver_ui/components/mech_anim_quad/index.html"),
        ("pneumo_solver_ui/components/corner_heatmap_live/index.html"),
        ("pneumo_solver_ui/components/minimap_live/index.html"),
        ("pneumo_solver_ui/components/road_profile_live/index.html"),
        ("pneumo_solver_ui/components/pneumo_svg_flow/index.html"),
        ("pneumo_solver_ui/components/playhead_ctrl/index.html"),
        ("pneumo_solver_ui/components/playhead_ctrl/index_unified_v1.html"),
    ]
    for rel in rels:
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "__frameInParentViewport" in src, rel
        assert "__nextIdleMs" in src, rel


def test_plotly_playhead_html_avoids_unconditional_setinterval():
    src = (ROOT / "pneumo_solver_ui" / "plotly_playhead_html.py").read_text(encoding="utf-8")
    assert "setInterval(updatePlayhead, POLL_MS);" not in src
    assert "playheadLoop" in src


def test_worldroad_sine_amplitude_label_is_semantic_half_range():
    src = (ROOT / "pneumo_solver_ui" / "ui_scenario_ring.py").read_text(encoding="utf-8")
    assert "Амплитуда A (полуразмах), мм" in src
    assert "профиль идёт от" in src
    assert "полный размах p-p =" in src
    assert "A=100 мм" in src
