from pathlib import Path


def _read(rel: str) -> str:
    return Path(rel).read_text(encoding='utf-8')


EMBEDDED_HTML_SOURCES = [
    'pneumo_solver_ui/ui_flow_panel_helpers.py',
    'pneumo_solver_ui/ui_svg_html_builders.py',
]


def test_embedded_flow_widgets_keep_render_guard_state_in_helper_sources() -> None:
    texts = [_read(rel) for rel in EMBEDDED_HTML_SOURCES]
    assert sum(txt.count('lastRenderedIdx = -1') for txt in texts) >= 2
    assert sum(
        txt.count('const shouldRender = playing || (idx !== lastRenderedIdx) || (lastRenderedPlaying !== playing);')
        for txt in texts
    ) >= 2
    assert sum(txt.count('__frameInParentViewport') for txt in texts) >= 2
    for txt in texts:
        assert '__nextIdleMs(60000, 180000, 300000)' not in txt
