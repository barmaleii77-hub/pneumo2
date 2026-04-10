from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.tools.make_send_bundle import _build_send_bundle_readme, _format_anim_diag_error as bundle_format_error
from pneumo_solver_ui.tools.triage_report import _format_anim_diag_error as triage_format_error


ROOT = Path(__file__).resolve().parents[1]
MAKE_SEND_BUNDLE_PATH = ROOT / "pneumo_solver_ui" / "tools" / "make_send_bundle.py"
TRIAGE_REPORT_PATH = ROOT / "pneumo_solver_ui" / "tools" / "triage_report.py"


def _missing_numpy_error() -> ModuleNotFoundError:
    exc = ModuleNotFoundError("No module named 'numpy'")
    exc.name = "numpy"
    return exc


def test_anim_diagnostics_dependency_errors_are_human_readable() -> None:
    exc = _missing_numpy_error()

    assert bundle_format_error(exc) == "Отсутствует необязательная зависимость: numpy"
    assert triage_format_error(exc) == "Отсутствует необязательная зависимость: numpy"


def test_send_bundle_readme_keeps_clean_russian_text() -> None:
    readme = _build_send_bundle_readme(
        {
            "anim_latest_available": False,
            "anim_latest_usable": False,
            "anim_latest_issues": ["Не удалось собрать anim_latest diagnostics: Отсутствует необязательная зависимость: numpy."],
        }
    )

    assert "Этот ZIP сформирован автоматически" in readme
    assert "Отсутствует необязательная зависимость: numpy" in readme
    for bad in ("вЂ", "в†", "Рђ", "РЎ", "????"):
        assert bad not in readme


def test_diagnostics_source_files_keep_clean_russian_literals() -> None:
    bundle_text = MAKE_SEND_BUNDLE_PATH.read_text(encoding="utf-8")
    triage_text = TRIAGE_REPORT_PATH.read_text(encoding="utf-8")

    assert "Этот ZIP сформирован автоматически" in bundle_text
    assert "Отсутствует необязательная зависимость" in bundle_text
    assert "Отсутствует необязательная зависимость" in triage_text
    for text in (bundle_text, triage_text):
        for bad in ("вЂ", "в†", "Рђ", "РЎ", "????"):
            assert bad not in text
