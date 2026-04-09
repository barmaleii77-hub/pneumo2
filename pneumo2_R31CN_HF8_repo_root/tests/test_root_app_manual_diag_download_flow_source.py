from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_root_app_manual_diag_build_offers_immediate_download_without_forced_rerun() -> None:
    text = (ROOT / "app.py").read_text(encoding="utf-8")

    assert 'download_diagnostic_zip_now' in text
    assert 'ZIP уже сохранён на диск' in text
    assert 'build_full_diagnostics_bundle' in text
    assert 'read_last_meta_from_out_dir' in text
    assert 'summarize_last_bundle_meta' in text
    assert '_diag_bundle_summary_lines' in text
    assert 'Anim pointer diagnostics:' in text
    assert 'st.rerun()' not in text[text.find('btn_diag_build_bundle'):text.find('UI performance settings')]
    assert 'st.experimental_rerun()' not in text[text.find('btn_diag_build_bundle'):text.find('UI performance settings')]
