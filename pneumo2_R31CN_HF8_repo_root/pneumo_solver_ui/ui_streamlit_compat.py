# -*- coding: utf-8 -*-
"""ui_streamlit_compat.py

Мелкая совместимость Streamlit между версиями.

Зачем
-----
В проекте встречаются разные окружения Streamlit. В одних версиях используется
`use_container_width=True`, в более новых — параметр `width="stretch"`.
Если передать «неизвестный» аргумент, Streamlit падает с TypeError.

Эта прослойка:
- конвертирует width<->use_container_width, где это возможно;
- удаляет неподдерживаемые параметры (hide_index/on_select/selection_mode);
- включает «растягивание» таблиц на ширину контейнера по умолчанию.

Важно
------
Это best-effort. Если Streamlit меняет внутренние API, патч не должен ломать
приложение: в худшем случае совместимость просто не включится.
"""

from __future__ import annotations

import inspect
from typing import Any, Dict, Optional


def _supports(sig: Optional[inspect.Signature], name: str) -> bool:
    try:
        return sig is not None and name in sig.parameters
    except Exception:
        return False


def _patch_width_kwargs(sig: Optional[inspect.Signature], kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize width/use_container_width across Streamlit versions."""
    if kwargs is None:
        return {}

    supports_width = _supports(sig, "width")
    supports_ucw = _supports(sig, "use_container_width")

    # width -> use_container_width
    if "width" in kwargs and (not supports_width) and supports_ucw:
        w = kwargs.pop("width", None)
        if isinstance(w, str) and w.lower() == "stretch":
            kwargs["use_container_width"] = True

    # use_container_width -> width
    if "use_container_width" in kwargs and (not supports_ucw) and supports_width:
        ucw = kwargs.pop("use_container_width", None)
        if bool(ucw):
            kwargs["width"] = "stretch"

    # If both are present, prefer width (new API) but keep explicit caller intent.
    if supports_width and ("width" not in kwargs) and ("use_container_width" in kwargs):
        # Caller used legacy kw on new API: map True->stretch to avoid warnings.
        try:
            ucw = bool(kwargs.pop("use_container_width"))
            if ucw:
                kwargs["width"] = "stretch"
        except Exception:
            # if anything goes wrong, keep original
            pass

    return kwargs


def _drop_unsupported(sig: Optional[inspect.Signature], kwargs: Dict[str, Any], keys) -> Dict[str, Any]:
    if kwargs is None:
        return {}
    for k in keys:
        if k in kwargs and (not _supports(sig, k)):
            kwargs.pop(k, None)
    return kwargs


_INSTALLED = False


def install_streamlit_compat(st_mod=None) -> bool:
    """Patch Streamlit methods in-place.

    Returns True if patch applied (or already applied), False otherwise.
    """
    global _INSTALLED
    if _INSTALLED:
        return True

    try:
        # Optional import; do not hard-crash if Streamlit isn't present.
        import streamlit as _st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return False

    st_mod = st_mod or _st

    def _wrap_method(method_name: str, *, default_stretch: bool) -> None:
        try:
            orig = getattr(DeltaGenerator, method_name)
        except Exception:
            return

        try:
            sig = inspect.signature(orig)
        except Exception:
            sig = None

        # Avoid double-wrapping
        if getattr(orig, "_pneumo_compat_wrapped", False):
            return

        def wrapped(self, *args, **kwargs):
            try:
                # Convert width / use_container_width
                kwargs = _patch_width_kwargs(sig, kwargs)

                # Drop unsupported common args
                if method_name in {"dataframe", "data_editor"}:
                    kwargs = _drop_unsupported(sig, kwargs, ["hide_index"])

                if method_name == "dataframe":
                    kwargs = _drop_unsupported(sig, kwargs, ["on_select", "selection_mode"])

                # Default stretch only for tables/editors (not for buttons!)
                if default_stretch and ("width" not in kwargs) and ("use_container_width" not in kwargs):
                    if _supports(sig, "width"):
                        kwargs["width"] = "stretch"
                    elif _supports(sig, "use_container_width"):
                        kwargs["use_container_width"] = True
            except Exception:
                # Never break UI because of compat layer.
                pass

            return orig(self, *args, **kwargs)

        wrapped._pneumo_compat_wrapped = True  # type: ignore[attr-defined]
        try:
            setattr(DeltaGenerator, method_name, wrapped)
        except Exception:
            pass

    # Tables/editors: stretch by default
    _wrap_method("dataframe", default_stretch=True)
    _wrap_method("data_editor", default_stretch=True)

    # Buttons: do NOT force stretch by default, only convert if caller passes width.
    _wrap_method("button", default_stretch=False)
    _wrap_method("download_button", default_stretch=False)

    _INSTALLED = True
    return True
