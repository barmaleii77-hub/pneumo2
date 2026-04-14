from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_diag_bootstrap_treats_known_optional_desktop_imports_as_low_noise() -> None:
    text = (ROOT / "pneumo_solver_ui" / "diag" / "bootstrap.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    for name in (
        "qdarktheme",
        "bottleneck",
        "cuda",
        "fqdn",
        "rfc3987",
        "rfc3986_validator",
        "rfc3987_syntax",
        "rfc3339_validator",
        "webcolors",
        "jsonpointer",
        "uri_template",
        "isoduration",
        "anywidget",
    ):
        assert f'"{name}"' in text
    assert "_OPTIONAL_MISSING_GENERIC" in text
