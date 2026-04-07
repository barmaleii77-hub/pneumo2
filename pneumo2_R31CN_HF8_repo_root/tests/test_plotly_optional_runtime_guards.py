from __future__ import annotations

from pathlib import Path


def test_compare_npz_web_has_plotly_import_guard() -> None:
    src = (Path(__file__).resolve().parents[1] / 'pneumo_solver_ui' / 'compare_npz_web.py').read_text(encoding='utf-8')

    assert '_HAS_PLOTLY = True' in src
    assert '_HAS_PLOTLY = False' in src
    assert 'Plotly не установлен в текущем окружении' in src
    assert 'render_compare_npz_web' in src


def test_validation_and_svg_pages_have_plotly_fallbacks() -> None:
    root = Path(__file__).resolve().parents[1]
    val_src = (root / 'pneumo_solver_ui' / 'validation_cockpit_web.py').read_text(encoding='utf-8')
    svg_src = (root / 'pneumo_solver_ui' / 'pages' / '16_PneumoScheme_Graph.py').read_text(encoding='utf-8')

    assert '_plot_small_multiples_matplotlib' in val_src
    assert '_plot_valves_heatmap_matplotlib' in val_src
    assert 'Plotly не установлен в текущем окружении. Страница продолжит работать' in val_src

    assert '_plot_polylines_matplotlib' in svg_src
    assert 'st.pyplot(fig, clear_figure=True)' in svg_src
