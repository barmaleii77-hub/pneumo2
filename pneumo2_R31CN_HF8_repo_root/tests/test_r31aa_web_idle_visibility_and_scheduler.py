from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

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


def test_embedded_html_widgets_use_long_idle_sleep_in_pause() -> None:
    for rel in ['pneumo_solver_ui/app.py', 'pneumo_solver_ui/pneumo_ui_app.py']:
        src = (ROOT / rel).read_text(encoding='utf-8')
        assert src.count('__frameInParentViewport') >= 2, rel
        assert src.count('__nextIdleMs(60000, 180000, 300000)') >= 2, rel
        assert '__nextIdleMs(3500, 10000, 12000)' not in src, rel


def test_browser_followers_no_longer_poll_every_4p5s_or_5s_in_pause() -> None:
    for rel in VISIBILITY_COMPONENTS:
        src = (ROOT / rel).read_text(encoding='utf-8')
        assert '__nextIdleMs(60000, 180000, 300000)' in src, rel
        assert '__nextIdleMs(4500, 12000, 15000)' not in src, rel
        assert '__nextIdleMs(5000, 12000, 15000)' not in src, rel
