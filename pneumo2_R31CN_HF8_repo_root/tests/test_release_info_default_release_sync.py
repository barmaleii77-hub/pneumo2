from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _version_release() -> str:
    return ROOT.joinpath('VERSION.txt').read_text(encoding='utf-8').splitlines()[0].strip()


def test_default_release_matches_version_txt_and_not_stale_r174(monkeypatch) -> None:
    monkeypatch.delenv('PNEUMO_RELEASE', raising=False)
    mod = importlib.import_module('pneumo_solver_ui.release_info')
    mod = importlib.reload(mod)
    expected = _version_release()
    assert mod.DEFAULT_RELEASE == expected
    assert mod.get_release() == expected
    assert 'R174' not in expected


def test_release_info_source_tracks_version_txt() -> None:
    src = ROOT.joinpath('pneumo_solver_ui', 'release_info.py').read_text(encoding='utf-8')
    expected = _version_release()
    assert 'DEFAULT_RELEASE = "PneumoApp_v6_80_R174"' not in src
    assert f'DEFAULT_RELEASE = "{expected}"' in src
