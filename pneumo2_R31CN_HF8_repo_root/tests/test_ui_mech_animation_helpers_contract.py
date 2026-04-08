from __future__ import annotations

from pathlib import Path

import pandas as pd

from pneumo_solver_ui import ui_mech_animation_helpers as helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_mech_animation_helpers.py"


class _FakeExpander:
    def __enter__(self) -> "_FakeExpander":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeStreamlit:
    def __init__(self) -> None:
        self.captions: list[str] = []
        self.warnings: list[str] = []
        self.radios: list[dict[str, object]] = []
        self.expanders: list[tuple[str, bool]] = []
        self.downloads: list[dict[str, object]] = []

    def caption(self, text: str) -> None:
        self.captions.append(text)

    def warning(self, text: str) -> None:
        self.warnings.append(text)

    def radio(self, label: str, *, options, format_func, horizontal: bool, index: int, key: str) -> str:
        self.radios.append(
            {
                "label": label,
                "options": list(options),
                "add": format_func("add"),
                "replace": format_func("replace"),
                "horizontal": horizontal,
                "index": index,
                "key": key,
            }
        )
        return "replace"

    def expander(self, label: str, expanded: bool = False) -> _FakeExpander:
        self.expanders.append((label, expanded))
        return _FakeExpander()

    def download_button(self, label: str, *, data, file_name: str, mime: str) -> None:
        self.downloads.append(
            {
                "label": label,
                "data": data,
                "file_name": file_name,
                "mime": mime,
            }
        )


def test_render_mechanical_animation_intro_handles_empty_state_and_contract() -> None:
    fake_st = _FakeStreamlit()

    proceed = helpers.render_mechanical_animation_intro(fake_st, df_main=None)

    assert proceed is False
    assert fake_st.captions == [
        "Упрощённая анимация механики: фронтальный вид (крен) и боковой вид (тангаж). Показывает движение рамы/колёс и ход штока по данным df_main."
    ]
    assert fake_st.warnings == ["Нет df_main для анимации механики."]
    assert fake_st.radios == [
        {
            "label": "Клик по механике",
            "options": ["replace", "add"],
            "add": "Добавлять к выбору",
            "replace": "Заменять выбор",
            "horizontal": True,
            "index": 0,
            "key": "mech_click_mode",
        }
    ]


def test_render_mechanical_animation_intro_allows_render_when_time_column_present() -> None:
    fake_st = _FakeStreamlit()
    df_main = pd.DataFrame({"время_с": [0.0, 1.0]})

    proceed = helpers.render_mechanical_animation_intro(fake_st, df_main=df_main)

    assert proceed is True
    assert fake_st.warnings == []


def test_render_mechanical_scheme_asset_expander_delegates_to_shared_assets(tmp_path: Path) -> None:
    fake_st = _FakeStreamlit()
    safe_images: list[str] = []
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "mech_scheme.png").write_bytes(b"png")
    (assets_dir / "mech_scheme.svg").write_text("<svg/>", encoding="utf-8")

    helpers.render_mechanical_scheme_asset_expander(
        fake_st,
        base_dir=tmp_path,
        safe_image_fn=lambda path: safe_images.append(path),
    )

    assert fake_st.expanders == [("Показать исходную механическую схему (SVG/PNG)", False)]
    assert safe_images == [str(assets_dir / "mech_scheme.png")]
    assert fake_st.downloads == [
        {
            "label": "Скачать mech_scheme.svg",
            "data": b"<svg/>",
            "file_name": "mech_scheme.svg",
            "mime": "image/svg+xml",
        }
    ]


def test_entrypoints_use_shared_mechanical_animation_helpers() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_mech_animation_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_mech_animation_helpers import (" in heavy_text
    assert "render_mechanical_animation_intro(" in app_text
    assert "render_mechanical_animation_intro(" in heavy_text
    assert "render_mechanical_scheme_asset_expander(" in app_text
    assert "render_mechanical_scheme_asset_expander(" in heavy_text
    assert 'st.radio(\n                                "Клик по механике"' not in app_text
    assert 'st.radio(\n                            "Клик по механике"' not in heavy_text
    assert 'with st.expander("Показать исходную механическую схему (SVG/PNG)", expanded=False):' not in app_text
    assert 'with st.expander("Показать исходную механическую схему (SVG/PNG)", expanded=False):' not in heavy_text
    assert 'st.warning("Нет df_main для анимации механики.")' not in app_text
    assert 'st.warning("Нет df_main для анимации механики.")' not in heavy_text
    assert "st.download_button(" in helper_text
    assert '"Скачать mech_scheme.svg"' in helper_text
