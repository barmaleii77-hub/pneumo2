from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

COMPONENT_SCHEDULERS = {
    'pneumo_solver_ui/components/corner_heatmap_live/index.html': ('__clearScheduledLoop', '__scheduleLoop', '__wakeLoop'),
    'pneumo_solver_ui/components/minimap_live/index.html': ('__clearScheduledLoop', '__scheduleLoop', '__wakeLoop'),
    'pneumo_solver_ui/components/road_profile_live/index.html': ('__clearScheduledLoop', '__scheduleLoop', '__wakeLoop'),
    'pneumo_solver_ui/components/mech_anim_quad/index.html': ('__clearScheduledTick', '__scheduleTick', '__wakeTick'),
    'pneumo_solver_ui/components/mech_anim/index.html': ('__clearScheduledTick', '__scheduleTick', '__wakeTick'),
    'pneumo_solver_ui/components/mech_car3d/index.html': ('__clearScheduledRender', '__scheduleRender', '__wakeRender'),
    'pneumo_solver_ui/components/pneumo_svg_flow/index.html': ('__clearScheduledLoop', '__scheduleLoop', '__wakeLoop'),
    'pneumo_solver_ui/components/playhead_ctrl/index.html': ('__clearScheduledTick', '__scheduleTick', '__wakeTick'),
    'pneumo_solver_ui/components/playhead_ctrl/index_unified_v1.html': ('__clearScheduledTick', '__scheduleTick', '__wakeTick'),
}


def test_all_web_followers_use_single_flight_schedulers_and_perf_registry() -> None:
    for rel, markers in COMPONENT_SCHEDULERS.items():
        src = (ROOT / rel).read_text(encoding='utf-8')
        for marker in markers:
            assert marker in src, (rel, marker)
        assert 'cancelAnimationFrame' in src, rel
        assert 'clearTimeout' in src, rel
        assert "pneumo_perf_component::" in src, rel
        assert 'duplicate_guard_hits' in src, rel
        assert 'schedule_timeout_count' in src, rel


def test_playhead_ctrl_has_browser_perf_overlay_and_json_export() -> None:
    src = (ROOT / 'pneumo_solver_ui/components/playhead_ctrl/index.html').read_text(encoding='utf-8')
    assert 'id="btnPerf"' in src
    assert 'id="btnPerfJson"' in src
    assert 'id="perfBox"' in src
    assert 'collectPerfRegistrySnapshot' in src
    assert 'browser perf registry' in src
    assert 'browser_perf_' in src


def test_embedded_html_widgets_in_apps_use_single_flight_step_scheduler() -> None:
    for rel in ['pneumo_solver_ui/app.py', 'pneumo_solver_ui/pneumo_ui_app.py']:
        src = (ROOT / rel).read_text(encoding='utf-8')
        assert src.count('__clearScheduledStep') >= 2, rel
        assert src.count('__scheduleStep') >= 2, rel
        assert src.count('__wakeStep') >= 2, rel
        assert src.count("document.addEventListener('visibilitychange', () => { if (!document.hidden) __wakeStep(); });") >= 2, rel
