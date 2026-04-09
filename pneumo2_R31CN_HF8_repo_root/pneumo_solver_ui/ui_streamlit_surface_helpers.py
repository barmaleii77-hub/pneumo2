from __future__ import annotations

import hashlib
from contextlib import contextmanager
from typing import Any

import pandas as pd


def safe_dataframe(
    st_module: Any,
    df: Any,
    *,
    height: int = 240,
    hide_index: bool = False,
    fallback_write: bool = False,
) -> Any:
    """Render a dataframe across old and new Streamlit APIs."""
    try:
        return st_module.dataframe(df, width="stretch", height=height, hide_index=hide_index)
    except TypeError:
        pass

    try:
        return st_module.dataframe(df, width="stretch", height=height)
    except TypeError:
        pass

    try:
        return st_module.dataframe(df, use_container_width=True, height=height, hide_index=hide_index)
    except TypeError:
        pass

    try:
        return st_module.dataframe(df, use_container_width=True, height=height)
    except TypeError:
        if fallback_write:
            return st_module.write(df)
        raise


def safe_plotly_chart(
    st_module: Any,
    fig: Any,
    *,
    key: str | None = None,
    on_select: Any = None,
    selection_mode: Any = None,
) -> Any:
    """Render a Plotly chart across old and new Streamlit APIs."""
    base_kwargs: dict[str, Any] = {}
    if key is not None:
        base_kwargs["key"] = key

    kwargs = dict(base_kwargs)
    kwargs["width"] = "stretch"
    if on_select is not None:
        kwargs["on_select"] = on_select
    if selection_mode is not None:
        kwargs["selection_mode"] = selection_mode
    try:
        return st_module.plotly_chart(fig, **kwargs)
    except TypeError:
        pass

    try:
        return st_module.plotly_chart(fig, width="stretch", **base_kwargs)
    except TypeError:
        pass

    try:
        return st_module.plotly_chart(fig, use_container_width=True, **base_kwargs)
    except TypeError:
        return st_module.plotly_chart(fig, **base_kwargs)


def safe_image(
    st_module: Any,
    img: Any,
    *,
    caption: str | None = None,
    int_width_fallback: int | None = None,
) -> Any:
    """Render an image across old and new Streamlit APIs."""
    try:
        return st_module.image(img, caption=caption, width="stretch")
    except Exception:
        if int_width_fallback is not None:
            try:
                return st_module.image(img, caption=caption, width=int_width_fallback)
            except TypeError:
                pass
        return st_module.image(img, caption=caption, use_container_width=True)


@contextmanager
def ui_popover(st_module: Any, label: str, expanded: bool = False):
    """Popover if available, otherwise an expander."""
    pop = getattr(st_module, "popover", None)
    if callable(pop):
        with pop(label):
            yield
    else:
        with st_module.expander(label, expanded=expanded):
            yield


def safe_previewable_dataframe(
    st_module: Any,
    df: Any,
    *,
    height: int = 240,
    hide_index: bool = False,
    max_cols: int = 10,
    key: str = "",
) -> Any:
    """Render a dataframe, switching to preview + row-card mode when it is wide."""
    try:
        if df is None:
            st_module.info("Нет данных.")
            return None

        if not isinstance(df, pd.DataFrame):
            try:
                df = pd.DataFrame(df)
            except Exception:
                st_module.write(df)
                return None

        ncols = int(df.shape[1]) if hasattr(df, "shape") else 0
        nrows = int(df.shape[0]) if hasattr(df, "shape") else 0

        if ncols > int(max_cols):
            if not key:
                h = hashlib.md5((str(list(df.columns)) + f"::{nrows}x{ncols}").encode("utf-8")).hexdigest()[:10]
                key = f"wide_df_{h}"

            cols_preview = list(df.columns)[: int(max_cols)]
            st_module.caption(
                f"Таблица широкая: {ncols} колонок. "
                f"Показаны первые {len(cols_preview)}. "
                "Полные данные — в карточке строки ниже."
            )

            safe_dataframe(
                st_module,
                df[cols_preview],
                height=height,
                hide_index=hide_index,
                fallback_write=True,
            )

            with st_module.expander("Детали выбранной строки", expanded=False):
                if nrows <= 0:
                    st_module.info("Пустая таблица.")
                else:
                    if nrows <= 2000:
                        sel = st_module.slider(
                            "Выбор строки",
                            0,
                            max(0, nrows - 1),
                            0,
                            step=1,
                            key=f"{key}__row",
                        )
                    else:
                        sel = st_module.number_input(
                            "Номер строки",
                            min_value=0,
                            max_value=max(0, nrows - 1),
                            value=0,
                            step=1,
                            key=f"{key}__row",
                        )
                    try:
                        i = int(sel)
                    except Exception:
                        i = 0

                    label_cols = [
                        c
                        for c in ["id", "name", "имя", "параметр", "тест", "test", "финал", "поколение"]
                        if c in df.columns
                    ]
                    if label_cols:
                        try:
                            st_module.caption(f"Строка {i}: {label_cols[0]} = {df.iloc[i][label_cols[0]]}")
                        except Exception:
                            pass

                    try:
                        st_module.json(df.iloc[i].to_dict())
                    except Exception:
                        st_module.write(df.iloc[i])
            return None

        return safe_dataframe(st_module, df, height=height, hide_index=hide_index)
    except Exception:
        st_module.write(df)
        return None
