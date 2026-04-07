from __future__ import annotations

from pathlib import Path


def test_pneumo_scheme_mnemo_uses_cache_resource_for_detail_pickle() -> None:
    src = (Path(__file__).resolve().parents[1] / 'pneumo_solver_ui' / 'pages' / '15_PneumoScheme_Mnemo.py').read_text(encoding='utf-8')

    assert '@st.cache_resource(show_spinner=False)\ndef _load_gz_pickle' in src
    assert '@st.cache_data(show_spinner=False)\ndef _load_gz_pickle' not in src
    assert 'pneumo_model_mod.Node' in src
