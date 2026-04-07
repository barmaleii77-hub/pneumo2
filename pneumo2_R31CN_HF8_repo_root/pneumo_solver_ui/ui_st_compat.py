# -*- coding: utf-8 -*-
"""ui_st_compat.py

Небольшой слой совместимости для Streamlit API.

Почему нужно
-----------
В проекте исторически встречались вызовы с параметрами:
- `width="stretch"`
- `use_container_width=True`

Streamlit менял/расширял API:
- сначала долго существовал `use_container_width=True`;
- затем появился новый параметр `width` (например: `width="stretch"`),
  а `use_container_width` стал deprecated и выдаёт предупреждения.

Цель:
- не ломать UI при несовпадении версии Streamlit;
- сохранить поведение «растянуть на ширину контейнера»;
- убрать шумные предупреждения о `use_container_width` на новых версиях;
- работать best-effort: если патч не применился — приложение не падает.

Мы не меняем логику приложения и не делаем "магии" с данными —
только совместимость параметров.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, Dict


try:
    from streamlit.delta_generator import DeltaGenerator  # type: ignore
except Exception:  # pragma: no cover
    DeltaGenerator = None  # type: ignore


_INSTALLED = False
_ORIG: Dict[str, Callable[..., Any]] = {}


def _sig_has_param(fn: Callable[..., Any], name: str) -> bool:
    try:
        return name in inspect.signature(fn).parameters
    except Exception:
        return False


def _wrap(method_name: str) -> None:
    """Обёртка вокруг метода DeltaGenerator для совместимости width/use_container_width."""

    if DeltaGenerator is None:
        return
    if not hasattr(DeltaGenerator, method_name):
        return

    orig = getattr(DeltaGenerator, method_name)
    if method_name in _ORIG:
        return

    has_width = _sig_has_param(orig, "width")
    has_use_container = _sig_has_param(orig, "use_container_width")

    def wrapped(self: Any, *args: Any, **kwargs: Any):
        # Преобразуем параметры ДО вызова orig:
        # - если есть width=..., стараемся использовать именно его (чтобы не ловить warning).
        # - если width нет в сигнатуре, деградируем к use_container_width.
        kw = dict(kwargs)

        # 1) use_container_width -> width (на новых версиях) чтобы убрать warning
        if has_width and ("use_container_width" in kw):
            u = kw.pop("use_container_width")
            # Не перетираем явно заданный width
            if "width" not in kw:
                kw["width"] = "stretch" if bool(u) else "content"

        # 2) width="stretch"/"content" -> use_container_width (на старых версиях)
        w = kw.get("width")
        if isinstance(w, str):
            w_norm = w.strip().lower()
            if (not has_width) and (w_norm in {"stretch", "content"}):
                kw.pop("width", None)
                if has_use_container:
                    kw["use_container_width"] = bool(w_norm == "stretch")

        # 3) Если метод вообще не знает width=..., просто выбрасываем.
        if (not has_width) and ("width" in kw):
            kw.pop("width", None)

        # hide_index появлялся/пропадал в разных версиях
        try:
            return orig(self, *args, **kw)
        except TypeError:
            kw2 = dict(kw)
            kw2.pop("hide_index", None)
            try:
                return orig(self, *args, **kw2)
            except TypeError:
                # Самый последний шанс: только позиционные аргументы
                return orig(self, *args)

    _ORIG[method_name] = orig
    setattr(DeltaGenerator, method_name, wrapped)


def install_st_compat() -> bool:
    """Установить best-effort патч совместимости.

    Возвращает True, если патч установлен (или уже был установлен).
    """

    global _INSTALLED
    if _INSTALLED:
        return True

    try:
        # Табличные/графические элементы
        for name in (
            "dataframe",
            "data_editor",
            "table",
            "pyplot",
            "plotly_chart",
            "altair_chart",
            "vega_lite_chart",
            "line_chart",
            "area_chart",
            "bar_chart",
            "image",
            "page_link",
            # Кнопки тоже иногда содержат use_container_width
            "button",
            "download_button",
            "form_submit_button",
            "link_button",
        ):
            _wrap(name)

        _INSTALLED = True
        return True
    except Exception:
        return False


def is_installed() -> bool:
    return bool(_INSTALLED)
