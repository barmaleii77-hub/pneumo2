from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_send_bundle_pages_delegate_to_canonical_zip_page() -> None:
    legacy_paths = [
        ROOT / "pneumo_solver_ui" / "pages_legacy" / "98_SendBundle.py",
        ROOT / "pneumo_solver_ui" / "pages_legacy" / "nonascii_18680cfb.py",
        ROOT / "pneumo_solver_ui" / "pages_legacy" / "nonascii_f5ca7911.py",
    ]

    for path in legacy_paths:
        src = path.read_text(encoding="utf-8", errors="replace")
        assert '98_BuildBundle_ZIP.py' in src, str(path)
        assert 'runpy.run_path' in src, str(path)
