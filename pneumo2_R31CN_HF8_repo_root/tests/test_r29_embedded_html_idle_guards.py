from pathlib import Path


def _read(rel: str) -> str:
    return Path(rel).read_text(encoding='utf-8')


def test_app_embedded_flow_widgets_have_idle_render_guards() -> None:
    txt = _read('pneumo_solver_ui/app.py')
    assert txt.count('lastRenderedIdx = -1') >= 2
    assert txt.count('const shouldRender = playing || (idx !== lastRenderedIdx) || (lastRenderedPlaying !== playing);') >= 2
    assert txt.count('__frameInParentViewport') >= 2
    assert txt.count('__nextIdleMs(60000, 180000, 300000)') >= 2


def test_pneumo_ui_app_embedded_flow_widgets_have_idle_render_guards() -> None:
    txt = _read('pneumo_solver_ui/pneumo_ui_app.py')
    assert txt.count('lastRenderedIdx = -1') >= 2
    assert txt.count('const shouldRender = playing || (idx !== lastRenderedIdx) || (lastRenderedPlaying !== playing);') >= 2
    assert txt.count('__frameInParentViewport') >= 2
    assert txt.count('__nextIdleMs(60000, 180000, 300000)') >= 2
