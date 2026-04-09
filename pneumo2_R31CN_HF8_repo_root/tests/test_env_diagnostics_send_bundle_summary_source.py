from __future__ import annotations

from pathlib import Path


def test_env_diagnostics_page_surfaces_last_send_bundle_summary() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "pneumo_solver_ui" / "pages" / "99_EnvDiagnostics.py").read_text(encoding="utf-8")

    assert "read_last_meta_from_out_dir" in text
    assert "summarize_last_bundle_meta" in text
    assert "Каталог SEND bundle:" in text
    assert "Последний ZIP:" in text
    assert "Anim pointer diagnostics:" in text
