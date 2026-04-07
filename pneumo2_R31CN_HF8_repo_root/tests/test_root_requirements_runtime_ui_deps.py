from __future__ import annotations

from pathlib import Path


def _normalized_requirements(path: Path) -> set[str]:
    out: set[str] = set()
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        pkg = line.split(';', 1)[0].split('>=', 1)[0].split('==', 1)[0].strip().lower()
        out.add(pkg)
    return out


def test_root_requirements_include_runtime_ui_dependencies() -> None:
    root = Path(__file__).resolve().parents[1]
    pkgs = _normalized_requirements(root / 'requirements.txt')

    # Launcher installs only root requirements.txt, so UI/runtime-only deps
    # must also live here, not only in pneumo_solver_ui/requirements.txt.
    assert 'plotly' in pkgs
    assert 'openpyxl' in pkgs
    assert 'streamlit-autorefresh' in pkgs

    assert 'duckdb' in pkgs
