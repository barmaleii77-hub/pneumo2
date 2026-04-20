from __future__ import annotations

from pathlib import Path


def test_env_diagnostics_page_surfaces_last_send_bundle_summary() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "pneumo_solver_ui" / "pages" / "99_EnvDiagnostics.py").read_text(encoding="utf-8")

    assert "read_last_meta_from_out_dir" in text
    assert "summarize_last_bundle_meta" in text
    assert "Каталог архива проекта:" in text
    assert "Последний архив:" in text
    assert "Данные последней анимации:" in text
    assert "ok={last_meta.get('ok')}" not in text
    assert "trigger={last_meta.get('trigger')}" not in text
