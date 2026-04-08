from __future__ import annotations

from pathlib import Path
from typing import Any


def render_mechanical_animation_intro(st: Any, *, df_main) -> bool:
    st.caption(
        "Упрощённая анимация механики: фронтальный вид (крен) и боковой вид (тангаж). "
        "Показывает движение рамы/колёс и ход штока по данным df_main."
    )
    st.radio(
        "Клик по механике",
        options=["replace", "add"],
        format_func=lambda value: "Заменять выбор" if value == "replace" else "Добавлять к выбору",
        horizontal=True,
        index=0,
        key="mech_click_mode",
    )
    if df_main is None or "время_с" not in df_main.columns:
        st.warning("Нет df_main для анимации механики.")
        return False
    return True


def render_mechanical_scheme_asset_expander(
    st: Any,
    *,
    base_dir: Path,
    safe_image_fn: Any,
) -> None:
    with st.expander("Показать исходную механическую схему (SVG/PNG)", expanded=False):
        png_path = base_dir / "assets" / "mech_scheme.png"
        if png_path.exists():
            safe_image_fn(str(png_path))
        svg_path = base_dir / "assets" / "mech_scheme.svg"
        if svg_path.exists():
            st.download_button(
                "Скачать mech_scheme.svg",
                data=svg_path.read_bytes(),
                file_name="mech_scheme.svg",
                mime="image/svg+xml",
            )
