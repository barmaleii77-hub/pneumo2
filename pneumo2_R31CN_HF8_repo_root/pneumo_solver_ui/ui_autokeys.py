# -*- coding: utf-8 -*-
"""ui_autokeys.py

Автогенерация стабильных `key=` для Streamlit-виджетов.

Зачем
-----
В Streamlit состояние виджета хранится в `st.session_state` и привязано к его
`key` (или авто-ID, который Streamlit генерирует сам). Если `key` не задан,
авто-ID может быть:

- неудобным для нашей системы автосохранения (мы сохраняем только «полезные»
  ключи по префиксам);
- нестабильным при небольших правках текста/структуры страницы;
- непредсказуемым в многостраничных сценариях.

Требование проекта: **значения, введённые пользователем, не должны исчезать**
при refresh/повторном запуске. Для этого мы стремимся иметь явные ключи
(`ui_...`) у всех основных виджетов.

Как работает
------------
Мы аккуратно (best-effort) патчим методы Streamlit DeltaGenerator (checkbox,
selectbox, slider, ...). Если пользователь не передал `key=`, мы добавляем его
автоматически.

Важно про кнопки
---------------
Кнопки и submit-виджеты — это триггеры действий. Их нельзя сохранять между
перезапусками, иначе возможны «самонажатия» после автозагрузки.

Поэтому автоключи для кнопок начинаются с `btn_...` — их уже исключает
`ui_persistence`.
"""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path
from typing import Any, Callable, Dict, Tuple


try:
    from streamlit.delta_generator import DeltaGenerator  # type: ignore
except Exception:  # pragma: no cover
    DeltaGenerator = None  # type: ignore


_INSTALLED = False
_ORIG: Dict[str, Callable[..., Any]] = {}

# Счётчики вызовов для одинаковых callsite (например, в цикле)
_RUN_COUNTER: Dict[str, int] = {}

# repo root: .../<repo>/pneumo_solver_ui/ui_autokeys.py
_REPO_ROOT = Path(__file__).resolve().parents[1]


def reset_run_counters() -> None:
    """Сбросить счётчики автоключей.

    Вызывать в начале каждого прогона страницы (через ui_bootstrap).
    """

    _RUN_COUNTER.clear()


def _is_internal_frame(path: str) -> bool:
    p = (path or "").replace("\\", "/")
    if "/streamlit/" in p or p.endswith("streamlit/__init__.py"):
        return True
    if p.endswith("/pneumo_solver_ui/ui_autokeys.py"):
        return True
    if p.endswith("/pneumo_solver_ui/ui_tooltips_ru.py"):
        return True
    if p.endswith("/pneumo_solver_ui/ui_bootstrap.py"):
        return True
    return False


def _find_user_callsite() -> Tuple[str, int, str]:
    """Вернуть (rel_path, lineno, func) для первого не-internal фрейма."""
    try:
        for fr in inspect.stack()[2:]:
            fn = fr.filename
            if _is_internal_frame(fn):
                continue
            try:
                rel = str(Path(fn).resolve().relative_to(_REPO_ROOT))
            except Exception:
                rel = fn
            return rel, int(fr.lineno or 0), str(fr.function or "")
    except Exception:
        pass
    return "<unknown>", 0, ""


def _clean_label(label: Any) -> str:
    try:
        s = "" if label is None else str(label)
    except Exception:
        s = ""
    s = " ".join(s.split())
    if len(s) > 80:
        s = s[:80] + "…"
    return s


def _auto_key(kind: str, label: Any) -> str:
    rel, ln, fn = _find_user_callsite()
    lbl = _clean_label(label)
    base = f"{kind}|{rel}|{ln}|{fn}|{lbl}"
    h = hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()[:10]

    # Кнопки — отдельный префикс, чтобы ui_persistence не сохранял их как настройки.
    if kind in {"button", "download_button", "form_submit_button"}:
        stem = f"btn_auto_{kind}_{h}"
    else:
        stem = f"ui_auto_{kind}_{h}"

    n = _RUN_COUNTER.get(stem, 0)
    _RUN_COUNTER[stem] = n + 1
    return stem if n == 0 else f"{stem}_{n+1}"


def _wrap_method(method_name: str, kind: str) -> None:
    if DeltaGenerator is None:
        return
    if not hasattr(DeltaGenerator, method_name):
        return

    orig = getattr(DeltaGenerator, method_name)
    if method_name in _ORIG:
        return

    # Патчим только методы, у которых есть параметр key
    try:
        sig = inspect.signature(orig)
        if "key" not in sig.parameters:
            return
    except Exception:
        return

    def wrapped(self: Any, *args: Any, **kwargs: Any):
        try:
            key = kwargs.get("key")
            if key is None or (isinstance(key, str) and key.strip() == ""):
                label = args[0] if args else kwargs.get("label", "")
                kwargs["key"] = _auto_key(kind=kind, label=label)
        except Exception:
            # best-effort
            pass
        return orig(self, *args, **kwargs)

    _ORIG[method_name] = orig
    setattr(DeltaGenerator, method_name, wrapped)


def install_autokeys() -> None:
    """Установить патч автоключей (один раз на процесс)."""

    global _INSTALLED
    if _INSTALLED:
        return
    if DeltaGenerator is None:
        return

    # Базовый набор «настроечных» виджетов
    _wrap_method("checkbox", "checkbox")
    _wrap_method("toggle", "toggle")
    _wrap_method("radio", "radio")
    _wrap_method("selectbox", "selectbox")
    _wrap_method("multiselect", "multiselect")
    _wrap_method("slider", "slider")
    _wrap_method("select_slider", "select_slider")
    _wrap_method("number_input", "number_input")
    _wrap_method("text_input", "text_input")
    _wrap_method("text_area", "text_area")
    _wrap_method("date_input", "date_input")
    _wrap_method("time_input", "time_input")

    # Табличные вводы
    _wrap_method("data_editor", "data_editor")

    # Триггеры
    _wrap_method("button", "button")
    _wrap_method("download_button", "download_button")
    _wrap_method("form_submit_button", "form_submit_button")

    _INSTALLED = True
