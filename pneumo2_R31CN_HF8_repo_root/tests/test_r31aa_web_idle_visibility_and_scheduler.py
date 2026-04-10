from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EMBEDDED_HTML_SOURCES = [
    'pneumo_solver_ui/ui_flow_panel_helpers.py',
    'pneumo_solver_ui/ui_svg_html_builders.py',
]

VISIBILITY_COMPONENTS = [
    'pneumo_solver_ui/components/mech_anim/index.html',
    'pneumo_solver_ui/components/mech_anim_quad/index.html',
    'pneumo_solver_ui/components/corner_heatmap_live/index.html',
    'pneumo_solver_ui/components/minimap_live/index.html',
    'pneumo_solver_ui/components/road_profile_live/index.html',
    'pneumo_solver_ui/components/pneumo_svg_flow/index.html',
    'pneumo_solver_ui/components/playhead_ctrl/index.html',
    'pneumo_solver_ui/components/playhead_ctrl/index_unified_v1.html',
    'pneumo_solver_ui/components/mech_car3d/index.html',
]


def test_web_followers_treat_zero_sized_or_css_hidden_iframes_as_offscreen() -> None:
    for rel in VISIBILITY_COMPONENTS:
        src = (ROOT / rel).read_text(encoding='utf-8')
        assert 'w <= 2 || h <= 2' in src, rel
        assert 'fe.clientWidth' in src and 'fe.clientHeight' in src, rel
        assert "cs.display === 'none'" in src, rel
        assert "cs.visibility === 'hidden'" in src, rel


def test_high_cost_components_use_single_flight_loop_schedulers() -> None:
    checks = {
        'pneumo_solver_ui/components/mech_anim/index.html': ('__clearScheduledTick', '__scheduleTick', '__wakeTick'),
        'pneumo_solver_ui/components/mech_car3d/index.html': ('__clearScheduledRender', '__scheduleRender', '__wakeRender'),
        'pneumo_solver_ui/components/pneumo_svg_flow/index.html': ('__clearScheduledLoop', '__scheduleLoop', '__wakeLoop'),
    }
    for rel, markers in checks.items():
        src = (ROOT / rel).read_text(encoding='utf-8')
        for marker in markers:
            assert marker in src, (rel, marker)
        assert 'cancelAnimationFrame' in src, rel
        assert 'clearTimeout' in src, rel


def test_mech_car3d_and_mech_anim_no_longer_start_parallel_wake_loops() -> None:
    mech_anim = (ROOT / 'pneumo_solver_ui/components/mech_anim/index.html').read_text(encoding='utf-8')
    assert "window.addEventListener('focus', () => { try {" in mech_anim
    assert '__wakeTick();' in mech_anim
    assert "document.addEventListener('visibilitychange', () => { if (!document.hidden) { try {" in mech_anim
    assert "__perfBump('focus_wakeups')" in mech_anim
    assert "__perfBump('visibility_wakeups')" in mech_anim

    car3d = (ROOT / 'pneumo_solver_ui/components/mech_car3d/index.html').read_text(encoding='utf-8')
    assert '__wakeRender();' in car3d
    assert 'markDirty(); __wakeRender();' in car3d
    assert "__perfBump('focus_wakeups')" in car3d


def test_embedded_html_widgets_stop_idle_polling_and_wake_on_visibility_events() -> None:
    for rel in EMBEDDED_HTML_SOURCES:
        src = (ROOT / rel).read_text(encoding='utf-8')
        assert '__frameInParentViewport' in src, rel
        assert '__wakeStep' in src, rel
        assert "window.addEventListener('scroll'" in src, rel
        assert "window.addEventListener('resize'" in src, rel
        assert 'visibilitychange' in src, rel
        assert '__nextIdleMs(60000, 180000, 300000)' not in src, rel
        assert '__nextIdleMs(3500, 10000, 12000)' not in src, rel


def test_browser_followers_no_longer_poll_while_paused_and_offscreen() -> None:
    for rel in VISIBILITY_COMPONENTS:
        src = (ROOT / rel).read_text(encoding='utf-8')
        assert 'addEventListener("focus"' in src or "addEventListener('focus'" in src, rel
        assert 'visibilitychange' in src, rel
        assert '__nextIdleMs(4500, 12000, 15000)' not in src, rel
        assert '__nextIdleMs(5000, 12000, 15000)' not in src, rel
        assert '__nextIdleMs(60000, 180000, 300000)' not in src, rel
