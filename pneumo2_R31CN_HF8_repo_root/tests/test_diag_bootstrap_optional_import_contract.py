from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_diag_bootstrap_treats_known_optional_desktop_imports_as_low_noise() -> None:
    text = (ROOT / "pneumo_solver_ui" / "diag" / "bootstrap.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert '"qdarktheme"' in text
    assert '"bottleneck"' in text
    assert '"cuda"' in text
    assert "_OPTIONAL_MISSING_GENERIC" in text
